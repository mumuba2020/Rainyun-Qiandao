import logging
import os
import random
import re
import time
import subprocess
import sys
import json
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

warnings.filterwarnings('ignore')

import cv2
import ddddocr
import requests
import ICR

_http_session = None
_http_session_lock = threading.Lock()

def mask_username(user):
    if not user:
        return ""
    if len(user) <= 4:
        return user[0] + "*" * (len(user) - 1)
    return user[:2] + "*" * (len(user) - 4) + user[-2:]

def get_http_session():
    global _http_session
    if _http_session is None:
        with _http_session_lock:
            if _http_session is None:
                _http_session = requests.Session()
                adapter = requests.adapters.HTTPAdapter(
                    pool_connections=10,
                    pool_maxsize=20,
                    max_retries=3
                )
                _http_session.mount('http://', adapter)
                _http_session.mount('https://', adapter)
    return _http_session

from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
# --- 修复1：正确的 webdriver_manager 导入 ---
try:
    from webdriver_manager.chrome import ChromeDriverManager
    try:
        from webdriver_manager.core.utils import ChromeType
    except ImportError:
        try:
            from webdriver_manager.chrome import ChromeType
        except ImportError:
            ChromeType = None
except ImportError:
    print("webdriver_manager未安装，将使用备用方式")
    ChromeDriverManager = None
    ChromeType = None

# --- 修复2：确保 notify 正常导入 ---
try:
    from notify import send
    print("已加载通知模块 (notify.py)")
except ImportError:
    print("警告: 未找到 notify.py，将无法发送通知。")
    def send(*args, **kwargs):
        pass

def generate_random_fingerprint():
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    ]
    
    resolutions = [
        "1920,1080",
        "1920,1200",
        "2560,1440",
        "1440,900",
        "1366,768",
        "1536,864"
    ]
    
    languages = [
        "zh-CN",
        "zh-CN,zh;q=0.9,en;q=0.8",
        "en-US,en;q=0.9,zh;q=0.8"
    ]
    
    timezones = [
        "Asia/Shanghai",
        "Asia/Hong_Kong",
        "Asia/Taipei",
        "Asia/Singapore"
    ]
    
    return {
        "user_agent": random.choice(user_agents),
        "resolution": random.choice(resolutions),
        "language": random.choice(languages),
        "timezone": random.choice(timezones)
    }

_selenium_init_lock = threading.Lock()

def init_selenium(debug=False, headless=False, fingerprint=None):
    if fingerprint is None:
        fingerprint = generate_random_fingerprint()
    
    ops = webdriver.ChromeOptions()
    
    is_github_actions = os.environ.get("GITHUB_ACTIONS", "false") == "true"
    
    if headless or is_github_actions:
        ops.add_argument('--headless=new')
        ops.add_argument('--no-sandbox')
        ops.add_argument('--disable-dev-shm-usage')
        ops.add_argument('--disable-gpu')
        ops.add_argument('--disable-software-rasterizer')
    
    ops.add_argument('--disable-blink-features=AutomationControlled')
    ops.add_argument('--no-proxy-server')
    
    ops.add_argument(f'--lang={fingerprint["language"]}')
    ops.add_argument(f'--user-agent={fingerprint["user_agent"]}')
    ops.add_argument('--disable-infobars')
    ops.add_argument('--disable-extensions')
    ops.add_argument('--disable-notifications')
    ops.add_argument('--disable-popup-blocking')
    ops.add_argument('--disable-translate')
    ops.add_argument('--disable-sync')
    ops.add_argument('--no-first-run')
    ops.add_argument('--disable-background-networking')
    ops.add_argument('--disable-component-update')
    ops.add_argument('--disable-domain-reliability')
    ops.add_argument('--ignore-certificate-errors')
    ops.add_argument('--log-level=3')
    ops.add_argument('--mute-audio')
    ops.add_argument('--window-size=1920,1080')
    
    if is_github_actions:
        ops.add_argument('--disable-features=VizDisplayCompositor')
        ops.add_argument('--disable-features=IsolateOrigins,site-per-process')
    
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2
    }
    ops.add_experimental_option("prefs", prefs)
    ops.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    ops.add_experimental_option('useAutomationExtension', False)
    
    if debug and not is_github_actions:
        ops.add_experimental_option("detach", True)
    
    driver = None
    
    local_chromedriver_paths = [
        os.path.expanduser("~/.local/bin/chromedriver.exe"),
        os.path.expanduser("~/.local/bin/chromedriver"),
        os.path.join(os.path.dirname(__file__), "chromedriver.exe"),
        os.path.join(os.path.dirname(__file__), "chromedriver"),
    ]
    
    local_driver_path = None
    for path in local_chromedriver_paths:
        if os.path.isfile(path):
            local_driver_path = path
            print(f"找到本地ChromeDriver: {local_driver_path}")
            break
    
    with _selenium_init_lock:
        time.sleep(0.5)
        
        if is_github_actions:
            debug_port = random.randint(9222, 9322)
            ops.add_argument(f'--remote-debugging-port={debug_port}')
            ops.add_argument('--disable-features=VizDisplayCompositor')
            
            try:
                print(f"GitHub Actions环境：使用系统ChromeDriver (端口: {debug_port})")
                driver = webdriver.Chrome(options=ops)
            except Exception as e:
                print(f"系统ChromeDriver失败: {e}")
                raise Exception(f"GitHub Actions环境初始化Selenium失败: {e}")
        elif local_driver_path:
            try:
                print(f"使用本地ChromeDriver: {local_driver_path}")
                service = Service(local_driver_path)
                driver = webdriver.Chrome(service=service, options=ops)
            except Exception as e:
                print(f"本地ChromeDriver失败: {e}")
        elif ChromeDriverManager:
            try:
                print("尝试使用webdriver-manager...")
                if ChromeType and hasattr(ChromeType, 'GOOGLE'):
                    manager = ChromeDriverManager(chrome_type=ChromeType.GOOGLE)
                else:
                    manager = ChromeDriverManager()
                driver_path = manager.install()
                if os.path.isfile(driver_path) and not driver_path.endswith('.chromedriver'):
                    import stat
                    if not os.access(driver_path, os.X_OK):
                        os.chmod(driver_path, os.stat(driver_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                    service = Service(driver_path)
                    driver = webdriver.Chrome(service=service, options=ops)
                else:
                    print(f"webdriver-manager返回无效路径: {driver_path}")
            except Exception as e:
                print(f"webdriver-manager失败: {e}")

        if driver is None:
            try:
                print("尝试使用系统ChromeDriver...")
                driver = webdriver.Chrome(options=ops)
            except Exception as e:
                print(f"系统ChromeDriver失败: {e}")
                raise Exception("无法初始化Selenium WebDriver")
    
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(30)
    driver.implicitly_wait(5)
    
    return driver

def safe_get(driver, url, max_retries=3, timeout=20):
    from selenium.common.exceptions import TimeoutException as SeleniumTimeoutException
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    for attempt in range(max_retries):
        try:
            driver.set_page_load_timeout(timeout)
            driver.get(url)
            WebDriverWait(driver, 5).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            return True
        except SeleniumTimeoutException:
            logger.warning(f"页面加载超时 (尝试 {attempt + 1}/{max_retries}): {url}")
            try:
                driver.execute_script("window.stop();")
            except:
                pass
            if attempt < max_retries - 1:
                time.sleep(1)
        except Exception as e:
            logger.warning(f"页面加载异常 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                raise e
    return False

def get_cookie_file_path(user):
    cookie_dir = "cookies"
    os.makedirs(cookie_dir, exist_ok=True)
    user_hash = hashlib.md5(user.encode()).hexdigest()
    return os.path.join(cookie_dir, f"{user_hash}.json")

def save_cookies(driver, user):
    try:
        cookie_file = get_cookie_file_path(user)
        cookies = driver.get_cookies()
        with open(cookie_file, 'w') as f:
            json.dump(cookies, f)
        logger.info(f"Cookie已保存: {cookie_file}")
        return True
    except Exception as e:
        logger.error(f"保存Cookie失败: {e}")
        return False

def load_cookies(driver, user):
    try:
        cookie_file = get_cookie_file_path(user)
        if not os.path.exists(cookie_file):
            logger.info("未找到Cookie缓存")
            return False
        
        with open(cookie_file, 'r') as f:
            cookies = json.load(f)
        
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass
        
        logger.info(f"Cookie已加载: {cookie_file}")
        return True
    except Exception as e:
        logger.error(f"加载Cookie失败: {e}")
        return False

def delete_cookie_cache(user):
    try:
        cookie_file = get_cookie_file_path(user)
        if os.path.exists(cookie_file):
            os.remove(cookie_file)
            logger.info("已删除失效的Cookie缓存")
    except Exception as e:
        logger.error(f"删除Cookie缓存失败: {e}")

def check_cookie_valid(driver):
    try:
        safe_get(driver, "https://app.rainyun.com/account/dashboard")
        time.sleep(2)
        return "dashboard" in driver.current_url or "login" not in driver.current_url
    except Exception:
        return False

def download_image(url, filename):
    os.makedirs("temp", exist_ok=True)
    try:
        session = get_http_session()
        response = session.get(url, timeout=10, proxies={"http": None, "https": None}, verify=False)
        if response.status_code == 200:
            with open(os.path.join("temp", filename), "wb") as f:
                f.write(response.content)
            return True
        return False
    except Exception as e:
        logger.error(f"下载图片异常: {str(e)}")
        return False


def get_url_from_style(style):
    return re.search(r'url\(["\']?(.*?)["\']?\)', style).group(1)


def get_width_from_style(style):
    return re.search(r'width:\s*([\d.]+)px', style).group(1)


def get_height_from_style(style):
    return re.search(r'height:\s*([\d.]+)px', style).group(1)

# --- 修复3：process_captcha 需要使用全局变量 ---
def process_captcha():
    global ocr, det, wait, driver
    
    try:
        download_captcha_img()
        if check_captcha():
            logger.info("开始使用ICR识别验证码")
            result = ICR.main("temp/captcha.jpg", "temp/sprite.jpg")
            if result and len(result) > 0:
                captcha = cv2.imread("temp/captcha.jpg")
                for info in result:
                    rect = info['bg_rect']
                    x, y = int(rect[0] + (rect[2] / 2)), int(rect[1] + (rect[3] / 2))
                    logger.info(f"图案 {info['sprite_idx'] + 1} 位于 ({x}, {y})")
                    slideBg = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="slideBg"]')))
                    style = slideBg.get_attribute("style")
                    width_raw, height_raw = captcha.shape[1], captcha.shape[0]
                    width, height = float(get_width_from_style(style)), float(get_height_from_style(style))
                    x_offset, y_offset = float(-width / 2), float(-height / 2)
                    final_x, final_y = int(x_offset + x / width_raw * width), int(y_offset + y / height_raw * height)
                    ActionChains(driver).move_to_element_with_offset(slideBg, final_x, final_y).click().perform()
                confirm = wait.until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="tcStatus"]/div[2]/div[2]/div/div')))
                logger.info("提交验证码")
                confirm.click()
                time.sleep(5)
                result = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="tcOperation"]')))
                if result.get_attribute("class") == 'tc-opera pointer show-success':
                    logger.info("验证码通过")
                    return
                else:
                    logger.error("验证码未通过，正在重试")
            else:
                logger.error("ICR识别失败，正在重试")
        else:
            logger.error("当前验证码识别率低，尝试刷新")
        
        try:
             reload = driver.find_element(By.XPATH, '//*[@id="reload"]')
             time.sleep(2)
             reload.click()
             time.sleep(5)
             process_captcha()
        except:
             pass

    except TimeoutException:
        logger.error("获取验证码图片失败")
    except Exception as e:
        logger.error(f"处理验证码时发生错误: {e}")


def download_captcha_img():
    # 声明使用全局 wait
    global wait
    
    if os.path.exists("temp"):
        for filename in os.listdir("temp"):
            file_path = os.path.join("temp", filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.remove(file_path)
    slideBg = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="slideBg"]')))
    img1_style = slideBg.get_attribute("style")
    img1_url = get_url_from_style(img1_style)
    logger.info("开始下载验证码图片(1): " + img1_url)
    download_image(img1_url, "captcha.jpg")
    sprite = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="instruction"]/div/img')))
    img2_url = sprite.get_attribute("src")
    logger.info("开始下载验证码图片(2): " + img2_url)
    download_image(img2_url, "sprite.jpg")


def check_captcha() -> bool:
    global ocr
    
    if ICR is None:
        try:
            raw = cv2.imread("temp/sprite.jpg")
            if raw is None: return False
            
            gray = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F).var()
            if laplacian < 50: return False
                
            h, w = raw.shape[:2]
            for i in range(3):
                w_segment = w // 3
                start_x = max(0, w_segment * i + 2)
                end_x = min(w, w_segment * (i + 1) - 2)
                temp = raw[:, start_x:end_x]
                cv2.imwrite(f"temp/sprite_{i + 1}.jpg", temp)
                
                with open(f"temp/sprite_{i + 1}.jpg", mode="rb") as f:
                    temp_rb = f.read()
                try:
                    result = ocr.classification(temp_rb)
                    if result in ["0", "1"]: return False
                except Exception:
                    return False
            return True
        except Exception:
            return False
    else:
        try:
            raw = cv2.imread("temp/sprite.jpg")
            if raw is None: return False
            gray = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F).var()
            return laplacian >= 30
        except Exception:
            return False


def check_answer(d: dict) -> bool:
    flipped = dict()
    for key in d.keys():
        flipped[d[key]] = key
    if len(d.values()) != len(flipped.keys()):
        return False
    return True


def preprocess_image(image):
    blurred = cv2.GaussianBlur(image, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    return morph

def compute_similarity(img1_path, img2_path):
    img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
    if img1 is None or img2 is None: return 0.0, 0
    
    scale = 100.0 / max(img1.shape) if max(img1.shape) > 100 else 1.0
    img1 = cv2.resize(img1, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    scale = 100.0 / max(img2.shape) if max(img2.shape) > 100 else 1.0
    img2 = cv2.resize(img2, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    
    img1 = preprocess_image(img1)
    img2 = preprocess_image(img2)

    try:
        sift = cv2.SIFT_create()
        kp1, des1 = sift.detectAndCompute(img1, None)
        kp2, des2 = sift.detectAndCompute(img2, None)
        if des1 is None or des2 is None: return 0.0, 0

        flann = cv2.FlannBasedMatcher(dict(algorithm=1, trees=5), dict(checks=50))
        matches = flann.knnMatch(des1, des2, k=2)
        good = [m for m, n in matches if m.distance < 0.7 * n.distance]
        
        if len(good) == 0: return 0.0, 0
        feature_factor = min(1.0, len(kp1) / 100.0, len(kp2) / 100.0)
        match_ratio = len(good) / min(len(des1), len(des2))
        return match_ratio * 0.7 + feature_factor * 0.3, len(good)
    except Exception:
        return 0.0, 0


def sign_in_account(user, pwd, debug=False, headless=False, index=0):
    timeout = 15
    driver = None
    
    global ocr, det, wait 
    
    try:
        account_label = "***"
        logger.info(f"开始处理: {account_label}")
        
        if ICR is not None:
            logger.info("使用ICR模块进行验证码识别（旋转分析+模板匹配）")
        else:
            logger.info("初始化 ddddocr")
            ocr = ddddocr.DdddOcr(ocr=True, show_ad=False)
            det = ddddocr.DdddOcr(det=True, show_ad=False)
        
        fingerprint = generate_random_fingerprint()
        logger.info("初始化 Selenium")
        driver = init_selenium(debug=debug, headless=headless, fingerprint=fingerprint)
        
        globals()['driver'] = driver 
        
        try:
            with open("stealth.min.js", mode="r") as f: js = f.read()
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": js})
        except: pass
        
        logger.info("尝试使用Cookie缓存登录")
        safe_get(driver, "https://app.rainyun.com")
        if load_cookies(driver, user):
            driver.refresh()
            time.sleep(1)
            if check_cookie_valid(driver):
                logger.info("Cookie登录成功！")
                logger.info("正在转到赚取积分页")
                wait = WebDriverWait(driver, timeout)
                try:
                    safe_get(driver, "https://app.rainyun.com/account/reward/earn")
                    wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                    time.sleep(1)
                    
                    try:
                        completed = driver.find_elements(By.XPATH, "//span[contains(text(),'每日签到')]/following::span[contains(text(),'已完成')][1]")
                        if any(el.is_displayed() for el in completed):
                            logger.info("‘每日签到’显示已完成，跳过当前账号")
                            try:
                                points_raw = driver.find_element(By.XPATH, '//*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[1]/div[1]/div/p/div/h3').get_attribute("textContent")
                                current_points = int(''.join(re.findall(r'\d+', points_raw)))
                            except:
                                current_points = 0
                            return True, user, current_points, None
                    except Exception:
                        pass
                    
                    strategies = [
                        (By.XPATH, '//*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[2]/div/div/div/div[1]/div/div[1]/div/div[1]/div/span[2]/a'),
                        (By.XPATH, '//a[contains(@href, "earn") and contains(text(), "赚取")]'),
                        (By.CSS_SELECTOR, 'a[href*="earn"]')
                    ]
                    
                    earn = None
                    for by, selector in strategies:
                        try:
                            earn = wait.until(EC.element_to_be_clickable((by, selector)))
                            break
                        except: continue
                    
                    if earn:
                        driver.execute_script("arguments[0].scrollIntoView(true);", earn)
                        time.sleep(1)
                        logger.info("点击赚取积分")
                        driver.execute_script("arguments[0].click();", earn)
                        
                        try:
                            WebDriverWait(driver, 15, poll_frequency=0.25).until(
                                EC.visibility_of_element_located((By.ID, "tcaptcha_iframe_dy"))
                            )
                            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "tcaptcha_iframe_dy")))
                            logger.info("处理验证码")
                            process_captcha()
                            driver.switch_to.default_content()
                        except TimeoutException:
                            logger.info("未触发验证码，继续")
                            driver.switch_to.default_content()
                        
                        logger.info("赚取积分操作完成")
                    else:
                        driver.refresh()
                        time.sleep(1)
                except Exception as e:
                    logger.error(f"Cookie登录后操作出错: {e}")
                    pass
        
        if not check_cookie_valid(driver):
            logger.info("Cookie已失效，尝试重新登录")
            
            logger.info("发起登录请求")
            safe_get(driver, "https://app.rainyun.com/auth/login")
            wait = WebDriverWait(driver, timeout)
            
            time.sleep(2)
            
            try:
                page_source = driver.page_source
                logger.info(f"页面源码长度: {len(page_source)}")
                current_url = driver.current_url
                logger.info(f"当前URL: {current_url}")
                
                if "login" not in current_url.lower():
                    logger.warning(f"URL异常，期望包含login，实际: {current_url}")
            except Exception as e:
                logger.warning(f"获取页面信息失败: {e}")
            
            logger.info("等待登录表单加载...")
        else:
            logger.info("Cookie登录成功！")
            logger.info("正在转到赚取积分页")
            wait = WebDriverWait(driver, timeout)
            
            time.sleep(2)
        
        username_selectors = [
            (By.NAME, 'login-field'),
            (By.CSS_SELECTOR, 'input[name="login-field"]'),
            (By.CSS_SELECTOR, 'input[type="text"]'),
            (By.CSS_SELECTOR, 'input[placeholder*="用户"]'),
            (By.CSS_SELECTOR, 'input[placeholder*="账号"]'),
            (By.XPATH, '//input[@name="login-field"]'),
        ]
        
        password_selectors = [
            (By.NAME, 'login-password'),
            (By.CSS_SELECTOR, 'input[name="login-password"]'),
            (By.CSS_SELECTOR, 'input[type="password"]'),
            (By.XPATH, '//input[@name="login-password"]'),
        ]
        
        username = None
        password = None
        
        for by, selector in username_selectors:
            try:
                username = wait.until(EC.visibility_of_element_located((by, selector)))
                logger.info(f"找到用户名输入框: {selector}")
                break
            except TimeoutException:
                continue
            except Exception as e:
                logger.debug(f"选择器 {selector} 失败: {e}")
                continue
        
        if username is None:
            logger.error("无法找到用户名输入框")
            try:
                inputs = driver.find_elements(By.TAG_NAME, 'input')
                logger.info(f"页面共有 {len(inputs)} 个input元素")
                for i, inp in enumerate(inputs):
                    try:
                        inp_type = inp.get_attribute('type') or 'text'
                        inp_name = inp.get_attribute('name') or ''
                        inp_placeholder = inp.get_attribute('placeholder') or ''
                        logger.info(f"  input[{i}]: type={inp_type}, name={inp_name}, placeholder={inp_placeholder}")
                    except:
                        pass
            except Exception as e:
                logger.error(f"获取input元素失败: {e}")
            raise TimeoutException("无法找到用户名输入框")
        
        for by, selector in password_selectors:
            try:
                password = wait.until(EC.visibility_of_element_located((by, selector)))
                logger.info(f"找到密码输入框: {selector}")
                break
            except TimeoutException:
                continue
            except Exception as e:
                logger.debug(f"选择器 {selector} 失败: {e}")
                continue
        
        if password is None:
            raise TimeoutException("无法找到密码输入框")
        
        try:
            login_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="app"]/div[1]/div[1]/div/div[2]/fade/div/div/span/form/button')))
        except:
            try:
                login_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]')))
            except:
                login_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "登录") or contains(text(), "登 录")]')))
            
        username.clear()
        password.clear()
        logger.info("输入用户名...")
        username.send_keys(user)
        time.sleep(0.5)
        logger.info("输入密码...")
        password.send_keys(pwd)
        time.sleep(0.5)
        logger.info("点击登录按钮...")
        
        for click_retry in range(2):
            try:
                login_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[contains(@class, "btn-primary") and (contains(., "登录") or contains(., "登 录"))]')))
                driver.execute_script("arguments[0].click();", login_button)
                break
            except Exception as e:
                if click_retry < 2:
                    logger.warning(f"登录按钮点击失败，重试 ({click_retry + 1}/2)")
                    time.sleep(1)
                else:
                    raise TimeoutException("登录按钮点击失败")
        
        # 登录验证码
        try:
            wait.until(EC.visibility_of_element_located((By.ID, 'tcaptcha_iframe_dy')))
            logger.warning("触发验证码！")
            driver.switch_to.frame("tcaptcha_iframe_dy")
            process_captcha()
            driver.switch_to.default_content()
        except TimeoutException:
            logger.info("未触发验证码")
        except Exception as e:
            logger.warning(f"验证码处理异常: {e}")
            try:
                driver.switch_to.default_content()
            except:
                pass
        
        logger.info("等待登录结果...")
        login_success = False
        for i in range(20):
            time.sleep(0.5)
            try:
                current_url = driver.current_url
                logger.info(f"[{i+1}/20] 当前URL: {current_url}")
                if "dashboard" in current_url or "reward" in current_url:
                    login_success = True
                    logger.info("检测到登录成功（URL包含dashboard/reward）")
                    break
                if "login" not in current_url:
                    login_success = True
                    logger.info("检测到登录成功（URL已离开登录页）")
                    break
            except Exception as e:
                logger.warning(f"获取URL失败: {e}")
        
        if not login_success:
            logger.error("登录超时，检查页面状态...")
            try:
                page_source = driver.page_source[:500]
                logger.error(f"页面内容片段: {page_source}")
                error_elements = driver.find_elements(By.CSS_SELECTOR, '[class*="error"], [class*="alert"], [class*="message"]')
                for el in error_elements:
                    if el.is_displayed() and el.text.strip():
                        logger.error(f"发现错误信息: {el.text}")
            except Exception as e:
                logger.error(f"检查页面状态失败: {e}")
            delete_cookie_cache(user)
            return False, user, 0, "登录超时"
        
        logger.info("登录成功！")
        save_cookies(driver, user)
        logger.info("正在转到赚取积分页")
        
        try:
            safe_get(driver, "https://app.rainyun.com/account/reward/earn")
            wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            time.sleep(1)
            logger.info("赚取积分页面加载完成")
        except Exception as e:
            logger.error(f"跳转赚取积分页失败: {e}")
            delete_cookie_cache(user)
            return False, user, 0, f"跳转失败: {e}"

        try:
            claim_btns = driver.find_elements(By.XPATH, "//span[contains(text(),'每日签到')]/following::a[contains(@href,'/account/reward/earn')][1]")
            if any(el.is_displayed() for el in claim_btns):
                logger.info("检测到'每日签到'行的'领取奖励'，进入签到流程")
            else:
                completed = driver.find_elements(By.XPATH, "//span[contains(text(),'每日签到')]/following::span[contains(text(),'已完成')][1]")
                if any(el.is_displayed() for el in completed):
                    logger.info("'每日签到'显示已完成，跳过当前账号")
                    try:
                        points_raw = driver.find_element(By.XPATH, '//*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[1]/div[1]/div/p/div/h3').get_attribute("textContent")
                        current_points = int(''.join(re.findall(r'\d+', points_raw)))
                    except:
                        current_points = 0
                    return True, user, current_points, None
        except Exception as e:
            logger.warning(f"检查签到状态失败: {e}")

        strategies = [
            (By.XPATH, '//*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[2]/div/div/div/div[1]/div/div[1]/div/div[1]/div/span[2]/a'),
            (By.XPATH, '//a[contains(@href, "earn") and contains(text(), "赚取")]'),
            (By.CSS_SELECTOR, 'a[href*="earn"]')
        ]
        
        earn = None
        for by, selector in strategies:
            try:
                earn = wait.until(EC.element_to_be_clickable((by, selector)))
                logger.info("找到赚取积分按钮")
                break
            except: 
                continue
        
        if earn:
            driver.execute_script("arguments[0].scrollIntoView(true);", earn)
            time.sleep(1)
            logger.info("点击赚取积分")
            driver.execute_script("arguments[0].click();", earn)
            
            logger.info("等待验证码加载（如果有）...")
            
            try:
                WebDriverWait(driver, 15, poll_frequency=0.25).until(
                    EC.visibility_of_element_located((By.ID, "tcaptcha_iframe_dy"))
                )
                wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "tcaptcha_iframe_dy")))
                logger.info("处理验证码")
                process_captcha()
                driver.switch_to.default_content()
            except TimeoutException:
                logger.info("未触发验证码，继续")
                driver.switch_to.default_content()
            except Exception as e:
                logger.error(f"验证码处理过程出错: {e}")
                driver.switch_to.default_content()
            
            logger.info("赚取积分操作完成")
        else:
            logger.warning("未找到赚取积分按钮，尝试刷新页面")
            driver.refresh()
            time.sleep(1)
        
        driver.implicitly_wait(5)
        try:
            points_raw = driver.find_element(By.XPATH, '//*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[1]/div[1]/div/p/div/h3').get_attribute("textContent")
            current_points = int(''.join(re.findall(r'\d+', points_raw)))
            logger.info(f"当前剩余积分: {current_points} | 约为 {current_points / 2000:.2f} 元")
        except:
            current_points = 0
        
        logger.info("任务执行成功！")
        return True, user, current_points, None

    except Exception as e:
        logger.error(f"异常: {str(e)}", exc_info=True)
        delete_cookie_cache(user)
        return False, user, 0, str(e)
    finally:
        if driver:
            try: driver.quit()
            except: pass

if __name__ == "__main__":
    is_github_actions = os.environ.get("GITHUB_ACTIONS", "false") == "true"
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    headless = os.environ.get('HEADLESS', 'false').lower() == 'true'
    if is_github_actions: headless = True
    
    max_workers = 1
    max_retries = int(os.environ.get('MAX_RETRIES', '1'))
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    ocr = None
    det = None
    wait = None

    ver = "2.5 (ICR + Cookie)"
    logger.info("------------------------------------------------------------------")
    logger.info(f"雨云自动签到工作流 v{ver}")
    logger.info(f"最大重试次数: {max_retries}")
    logger.info("------------------------------------------------------------------")
    
    accounts = []
    users_env = os.environ.get("RAINYUN_USER", "")
    passwords_env = os.environ.get("RAINYUN_PASS", "")
    users = [user.strip() for user in users_env.split('\n') if user.strip()]
    passwords = [pwd.strip() for pwd in passwords_env.split('\n') if pwd.strip()]
    
    if len(users) == len(passwords) and len(users) > 0:
        for user, pwd in zip(users, passwords):
            accounts.append((user, pwd))
    else:
        logger.error("未找到有效账户配置或数量不匹配")
        exit(1)
    
    results = []
    
    def process_account(account_info):
        index, user, pwd = account_info
        thread_name = threading.current_thread().name
        account_label = f"账户{index + 1}"
        logger.info(f"[{thread_name}] === 开始处理 {account_label} ===")
        result = sign_in_account(user, pwd, debug=debug, headless=headless, index=index)
        logger.info(f"[{thread_name}] === {account_label} 处理完成 ===")
        return (index, result)
    
    current_retry = 0
    failed_accounts = [(i + 1, user, pwd) for i, (user, pwd) in enumerate(accounts)]
    
    while current_retry <= max_retries and failed_accounts:
        if current_retry > 0:
            logger.info(f"\n{'='*60}")
            logger.info(f"第 {current_retry} 轮重试，共 {len(failed_accounts)} 个失败账户")
            logger.info(f"{'='*60}\n")
            time.sleep(random.randint(5, 15))
        else:
            logger.info(f"开始并发处理 {len(failed_accounts)} 个账户...")
        
        account_infos = failed_accounts.copy()
        failed_accounts = []
        
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="Worker") as executor:
            future_to_account = {executor.submit(process_account, info): info for info in account_infos}
            
            results_dict = {}
            
            for future in as_completed(future_to_account):
                account_info = future_to_account[future]
                try:
                    index, result = future.result()
                    results_dict[index] = result
                    if not result[0]:
                        failed_accounts.append(account_info)
                except Exception as e:
                    logger.error(f"账户 {account_info[1]} 处理异常: {e}")
                    results_dict[account_info[0]] = (False, account_info[1], 0, str(e))
                    failed_accounts.append(account_info)
        
        current_retry += 1
    
    results = [results_dict.get(i, (False, accounts[i-1][0] if i <= len(accounts) else "", 0, "未处理")) for i in range(1, len(accounts) + 1)]
    
    logger.info("\n所有账户处理完成，生成统一通知...")
    
    success_count = sum(1 for r in results if r[0])
    total_count = len(accounts)
    
    if success_count == total_count:
        notification_title = f"✅ 雨云自动签到完成 - 全部成功"
    elif success_count > 0:
        notification_title = f"⚠️ 雨云自动签到完成 - 部分成功 ({success_count}/{total_count})"
    else:
        notification_title = f"❌ 雨云自动签到完成 - 全部失败"
    
    notification_content = f"雨云自动签到结果汇总：\n\n总账户数: {total_count}\n成功账户数: {success_count}\n失败账户数: {total_count - success_count}\n\n详细结果：\n"
    
    for i, (success, user, points, error_msg) in enumerate(results, 1):
        if success:
            notification_content += f"✅ {user}: 积分 {points} | 约 {points / 2000:.2f} 元\n"
        else:
            notification_content += f"❌ {user}: {error_msg}\n"
    
    try:
        send(notification_title, notification_content)
        logger.info("统一通知发送成功")
    except Exception as e:
        logger.warning("通知发送失败（未配置通知或配置错误）")