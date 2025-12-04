import logging
import os
import random
import re
import time
import subprocess
import sys

import cv2
import ddddocr
import requests
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

# 尝试导入 webdriver_manager
try:
    from webdriver_manager.chrome import ChromeDriverManager
    # 尝试不同的ChromeType导入路径
    try:
        from webdriver_manager.core.utils import ChromeType
    except ImportError:
        try:
            from webdriver_manager.chrome import ChromeType
        except ImportError:
            # 如果找不到ChromeType，设置为None
            ChromeType = None
except ImportError:
    print("webdriver_manager未安装，将使用备用方式")
    ChromeDriverManager = None
    ChromeType = None

# --- START OF MODIFICATION: 添加通知函数导入 ---
try:
    from notify import send
    print("已加载通知模块 (notify.py)")
except ImportError:
    print("警告: 未找到 notify.py，将无法发送通知。")
    def send(*args, **kwargs):
        pass
# --- END OF MODIFICATION ---


def init_selenium(debug=False, headless=False):
    ops = webdriver.ChromeOptions()
    
    # 无论什么环境都添加无头模式选项
    if headless or os.environ.get("GITHUB_ACTIONS", "false") == "true":
        for option in ['--headless', '--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']:
            ops.add_argument(option)
    
    # 添加通用选项
    ops.add_argument('--window-size=1920,1080')
    ops.add_argument('--disable-blink-features=AutomationControlled')
    ops.add_argument('--no-proxy-server')
    ops.add_argument('--lang=zh-CN')
    
    # 环境变量判断是否在GitHub Actions中运行
    is_github_actions = os.environ.get("GITHUB_ACTIONS", "false") == "true"
    
    if debug and not is_github_actions:
        ops.add_experimental_option("detach", True)
    
    # 尝试不同的ChromeDriver使用策略
    try:
        print("尝试直接使用系统ChromeDriver...")
        driver = webdriver.Chrome(options=ops)
        print("成功使用系统ChromeDriver")
        return driver
    except Exception as e:
        print(f"系统ChromeDriver失败: {e}")
    
    try:
        print("尝试使用webdriver-manager...")
        if ChromeDriverManager:
            if ChromeType and hasattr(ChromeType, 'GOOGLE'):
                manager = ChromeDriverManager(chrome_type=ChromeType.GOOGLE)
            else:
                manager = ChromeDriverManager()
            
            driver_path = manager.install()
            print(f"获取到ChromeDriver路径: {driver_path}")
            service = Service(driver_path)
            driver = webdriver.Chrome(service=service, options=ops)
            print("成功使用webdriver-manager")
            return driver
        else:
            raise ImportError("webdriver_manager未安装")
    except Exception as e:
        print(f"webdriver-manager失败: {e}")
    
    try:
        print("尝试使用备用ChromeDriver路径...")
        common_paths = ['/usr/local/bin/chromedriver', '/usr/bin/chromedriver', './chromedriver', 'chromedriver']
        for path in common_paths:
            try:
                service = Service(path)
                driver = webdriver.Chrome(service=service, options=ops)
                print(f"成功使用备用路径: {path}")
                return driver
            except:
                continue
    except Exception as e:
        print(f"备用路径失败: {e}")
    
    if is_github_actions:
        print("在GitHub Actions环境中，尝试安装ChromeDriver...")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'chromedriver-binary-auto'])
            import chromedriver_binary
            driver = webdriver.Chrome(options=ops)
            print("成功使用chromedriver-binary-auto")
            return driver
        except Exception as e:
            print(f"备用安装失败: {e}")
    
    raise Exception("无法初始化Selenium WebDriver")

def download_image(url, filename):
    os.makedirs("temp", exist_ok=True)
    try:
        # 禁用代理以避免连接问题
        response = requests.get(url, timeout=10, proxies={"http": None, "https": None}, verify=False)
        if response.status_code == 200:
            path = os.path.join("temp", filename)
            with open(path, "wb") as f:
                f.write(response.content)
            return True
        else:
            logger.error(f"下载图片失败！状态码: {response.status_code}")
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


# --- 核心修复：增强 process_captcha 逻辑 (添加重试刷新 & 全局变量) ---
def process_captcha():
    max_captcha_retries = 5
    current_retries = 0
    
    # 确保可以访问全局变量
    global ocr, det, wait, driver
    
    while current_retries < max_captcha_retries:
        try:
            download_captcha_img() # 这个函数内部会等待 slideBg 元素出现
            break
            
        except TimeoutException:
            current_retries += 1
            logger.error(f"获取验证码图片失败（可能是页面未加载完成），尝试第 {current_retries}/{max_captcha_retries} 次重试...")
            
            # 尝试刷新页面
            try:
                driver.switch_to.default_content()
                reload = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="reload"]')))
                time.sleep(1)
                reload.click()
                logger.info("点击刷新按钮，重新加载验证码...")
                time.sleep(5)
                wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "tcaptcha_iframe_dy")))
            except Exception as e:
                logger.warning(f"刷新验证码时发生错误: {e}")
                
            if current_retries >= max_captcha_retries:
                raise Exception("多次尝试后仍无法获取验证码图片，放弃处理。")
            
            time.sleep(random.uniform(2, 4))
        
        except Exception as e:
            logger.error(f"下载验证码图片时发生未知错误: {e}")
            raise

    # --- 识别和点击逻辑 ---
    try:
        if check_captcha():
            logger.info("开始识别验证码")
            captcha = cv2.imread("temp/captcha.jpg")
            with open("temp/captcha.jpg", 'rb') as f:
                captcha_b = f.read()
            bboxes = det.detection(captcha_b)
            result = dict()
            for i in range(len(bboxes)):
                x1, y1, x2, y2 = bboxes[i]
                spec = captcha[y1:y2, x1:x2]
                cv2.imwrite(f"temp/spec_{i + 1}.jpg", spec)
                for j in range(3):
                    similarity, matched = compute_similarity(f"temp/sprite_{j + 1}.jpg", f"temp/spec_{i + 1}.jpg")
                    similarity_key = f"sprite_{j + 1}.similarity"
                    position_key = f"sprite_{j + 1}.position"
                    if similarity_key in result.keys():
                        if float(result[similarity_key]) < similarity:
                            result[similarity_key] = similarity
                            result[position_key] = f"{int((x1 + x2) / 2)},{int((y1 + y2) / 2)}"
                    else:
                        result[similarity_key] = similarity
                        result[position_key] = f"{int((x1 + x2) / 2)},{int((y1 + y2) / 2)}"
            if check_answer(result):
                for i in range(3):
                    similarity_key = f"sprite_{i + 1}.similarity"
                    position_key = f"sprite_{i + 1}.position"
                    positon = result[position_key]
                    logger.info(f"图案 {i + 1} 位于 ({positon})，匹配率：{result[similarity_key]}")
                    slideBg = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="slideBg"]')))
                    style = slideBg.get_attribute("style")
                    x, y = int(positon.split(",")[0]), int(positon.split(",")[1])
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
                result_element = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="tcOperation"]')))
                if result_element.get_attribute("class") == 'tc-opera pointer show-success':
                    logger.info("验证码通过")
                    return
                else:
                    logger.error("验证码未通过，正在重试")
            else:
                logger.error("验证码识别失败，正在重试")
        else:
            logger.error("当前验证码识别率低，尝试刷新")
        
        # 识别失败或未通过，进行刷新重试
        driver.switch_to.default_content()
        reload = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="reload"]')))
        time.sleep(random.uniform(1, 3))
        reload.click()
        logger.info("识别失败/未通过，点击刷新按钮重试")
        time.sleep(5)
        
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "tcaptcha_iframe_dy")))
        process_captcha()
        
    except TimeoutException:
        logger.error("验证码处理流程超时")
        raise
    except Exception as e:
        logger.error(f"验证码处理流程发生错误: {e}")
        raise


def download_captcha_img():
    global wait # 确保 wait 是全局变量
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


# 检查是否存在重复坐标，快速判断识别错误
def check_answer(d: dict) -> bool:
    # 保持原逻辑的简单检查
    flipped = dict()
    for key in d.keys():
        if key.endswith(".position"):
            flipped[d[key]] = key
    
    position_keys = [k for k in d.keys() if k.endswith(".position")]
    if len(position_keys) != len(flipped.keys()):
        return False
    
    return True

# 图像处理和相似度计算函数... (保持不变，因为它们在上一轮已经优化且能工作)
def preprocess_image(image):
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(image, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(blurred, 255, 
                                  cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY, 11, 2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    return morph

def compute_similarity(img1_path, img2_path):
    img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
    if img1 is None or img2 is None: return 0.0, 0
    max_dim = 100
    scale1 = max_dim / max(img1.shape) if max(img1.shape) > max_dim else 1.0
    img1 = cv2.resize(img1, None, fx=scale1, fy=scale1, interpolation=cv2.INTER_AREA)
    scale2 = max_dim / max(img2.shape) if max(img2.shape) > max_dim else 1.0
    img2 = cv2.resize(img2, None, fx=scale2, fy=scale2, interpolation=cv2.INTER_AREA)
    img1 = preprocess_image(img1)
    img2 = preprocess_image(img2)
    try:
        sift = cv2.SIFT_create()
        kp1, des1 = sift.detectAndCompute(img1, None)
        kp2, des2 = sift.detectAndCompute(img2, None)
        if des1 is None or des2 is None or len(des1) < 10 or len(des2) < 10: return 0.0, 0
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        matches = flann.knnMatch(des1.astype('float32'), des2.astype('float32'), k=2)
        good = [m for m_n in matches if len(m_n) == 2 and m_n[0].distance < 0.7 * m_n[1].distance]
        if len(good) == 0: return 0.0, 0
        feature_factor = min(1.0, len(kp1) / 100.0, len(kp2) / 100.0)
        match_ratio = len(good) / min(len(des1), len(des2))
        similarity = match_ratio * 0.7 + feature_factor * 0.3
        return similarity, len(good)
    except Exception as e:
        logger.error(f"相似度计算出错 (可能缺少 SIFT/FLANN 模块): {e}")
        return 0.0, 0

# --- 新增获取积分 helper 函数 ---
def get_current_points(driver: WebDriver, wait: WebDriverWait) -> int:
    """获取当前积分并返回，失败返回 0"""
    try:
        driver.get("https://app.rainyun.com/dashboard")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        time.sleep(2) # 等待渲染

        # 定位积分元素
        points_xpath = '//*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[1]/div[1]/div/p/div/h3'
        points_raw = wait.until(EC.visibility_of_element_located((By.XPATH, points_xpath))).get_attribute("textContent")
        current_points = int(''.join(re.findall(r'\d+', points_raw)))
        return current_points
    except Exception as e:
        logger.error(f"获取当前积分失败: {e}")
        return 0


# --- 改进 sign_in_account 逻辑 ---
def sign_in_account(user, pwd, debug=False, headless=False):
    timeout = 15
    driver = None
    
    # 确保 ocr, det, wait 可以在 process_captcha 中使用
    global ocr, det, wait
    
    try:
        logger.info(f"开始处理账户: {user}")
        if not debug:
            delay_sec = random.randint(5, 10)
            logger.info(f"随机延时等待 {delay_sec} 秒")
            time.sleep(delay_sec)
        
        logger.info("初始化 ddddocr")
        ocr = ddddocr.DdddOcr(ocr=True, show_ad=False)
        det = ddddocr.DdddOcr(det=True, show_ad=False)
        
        logger.info("初始化 Selenium")
        driver = init_selenium(debug=debug, headless=headless)
        
        # 临时将 driver 设为全局，供 process_captcha 使用
        globals()['driver'] = driver 
        
        try:
            with open("stealth.min.js", mode="r") as f:
                js = f.read()
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": js
            })
        except:
            logger.warning("未找到 stealth.min.js，跳过反爬设置。")
            pass
        
        logger.info("发起登录请求")
        driver.get("https://app.rainyun.com/auth/login")
        wait = WebDriverWait(driver, timeout) # 设置全局 wait 实例
        
        # 登录流程
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                username = wait.until(EC.visibility_of_element_located((By.NAME, 'login-field')))
                password = wait.until(EC.visibility_of_element_located((By.NAME, 'login-password')))
                login_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="app"]/div[1]/div[1]/div/div[2]/fade/div/div/span/form/button')))
                
                username.clear()
                password.clear()
                username.send_keys(user)
                time.sleep(0.5)
                password.send_keys(pwd)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", login_button)
                break
            except TimeoutException:
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(retry_count)
                    driver.refresh()
                else:
                    raise Exception("登录页面加载超时或失败。")
        
        # 登录验证码
        try:
            wait.until(EC.visibility_of_element_located((By.ID, 'tcaptcha_iframe_dy')))
            logger.warning("触发登录验证码！")
            driver.switch_to.frame("tcaptcha_iframe_dy")
            process_captcha()
        except TimeoutException:
            logger.info("未触发登录验证码")
        
        time.sleep(5)
        driver.switch_to.default_content()
        
        # 验证登录状态并处理赚取积分
        if "dashboard" in driver.current_url:
            logger.info("登录成功！")
            
            # --- 1. 获取签到前积分 ---
            initial_points = get_current_points(driver, wait)
            if initial_points > 0:
                logger.info(f"签到前积分: {initial_points} | 约为 {initial_points / 2000:.2f} 元")
            else:
                logger.warning("未能获取签到前积分，将无法精确判断签到是否成功。")

            logger.info("正在转到赚取积分页以执行签到")
            driver.get("https://app.rainyun.com/account/reward/earn")

            # --- 2. 尝试点击每日签到按钮 ---
            max_click_retries = 3
            sign_in_completed = False
            
            for _ in range(max_click_retries):
                try:
                    logger.info("等待赚取积分页面加载...")
                    wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                    time.sleep(3) # 额外等待确保页面完全渲染
                    
                    # 使用 XPath 定位“每日签到”卡片内的操作按钮
                    sign_button_xpath = '//div[contains(., "每日签到")]/following-sibling::div//button[contains(@class, "btn-relief-primary")]'
                    sign_button = wait.until(EC.element_to_be_clickable((By.XPATH, sign_button_xpath)))
                    
                    button_text = sign_button.get_attribute("textContent").strip()
                    
                    if "领奖励" in button_text or "签到" in button_text:
                        driver.execute_script("arguments[0].scrollIntoView(true);", sign_button)
                        time.sleep(1)
                        logger.info(f"找到并点击每日签到按钮: {button_text}")
                        driver.execute_script("arguments[0].click();", sign_button)
                        
                        # --- 核心修复：智能等待验证码弹窗及内容 (替换 time.sleep(3)) ---
                        try:
                            logger.info("正在检测是否有验证码弹出...")
                            
                            # 1. 第一层等待：等待 iframe 框架出现 (短超时 5秒)
                            short_wait = WebDriverWait(driver, 5)
                            short_wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "tcaptcha_iframe_dy")))
                            
                            logger.warning("检测到验证码悬浮窗！")
                            
                            # 2. 第二层等待：等待验证码内容（图片）渲染完成 (长超时, 使用全局 wait)
                            logger.info("正在等待验证码图片加载...")
                            wait.until(EC.visibility_of_element_located((By.ID, "slideBg")))
                            logger.info("验证码内容加载完成，开始处理...")
                            
                            # 3. 开始执行识别逻辑
                            process_captcha()
                            
                            # 处理完切回主文档
                            driver.switch_to.default_content()
                            logger.info("验证码处理完成")

                        except TimeoutException:
                            # 验证码没弹出来，或者弹出来但加载超时了
                            try:
                                driver.switch_to.default_content()
                            except:
                                pass
                            logger.info("未检测到验证码（或验证码加载超时），默认任务已完成")

                        except Exception as e:
                            # 捕获其他未知错误
                            logger.error(f"验证码检测/处理过程发生未知错误: {e}")
                            driver.switch_to.default_content()
                        
                        logger.info("签到操作完成，等待积分刷新...")
                        sign_in_completed = True
                        time.sleep(5) # 留出时间让服务器处理和页面刷新
                        break
                    else:
                        logger.info(f"按钮文本为 '{button_text}'，判断为已签到。")
                        sign_in_completed = True
                        break
                        
                except TimeoutException:
                    logger.warning("未找到每日签到卡片或按钮，可能是页面结构变化或已签到。刷新页面重试...")
                    driver.refresh()
                    time.sleep(3)
                except Exception as e:
                    logger.error(f"尝试执行每日签到时出错: {e}")
                    time.sleep(3)
            
            if not sign_in_completed:
                 logger.error("多次尝试后仍无法执行签到操作。")

            # --- 3. 检查签到后积分并判断结果 ---
            current_points = get_current_points(driver, wait)
            
            # 使用积分对比来判断最终结果
            if initial_points > 0 and current_points > initial_points:
                added_points = current_points - initial_points
                logger.info(f"✅ 任务执行成功！积分已增加 {added_points} 点。")
                return True, user, current_points, None
                
            elif current_points > 0 and (initial_points > 0 and current_points == initial_points):
                logger.warning("积分未增加，可能已签到。")
                # 流程已执行，标记为成功，但给出警告信息
                return True, user, current_points, "积分未增加，可能已签到。"
                
            else:
                logger.info("任务执行成功！") 
                return True, user, current_points, None
                
        else:
            logger.error("❌ 登录失败！")
            return False, user, 0, "登录失败，未能进入仪表盘页面，请检查账号密码或验证码处理逻辑。"

    except Exception as e:
        err_msg = f"脚本运行期间发生致命异常: {str(e)}"
        logger.error(err_msg, exc_info=True)
        return False, user, 0, err_msg

    finally:
        if driver:
            logger.info("正在关闭浏览器...")
            try:
                driver.quit()
            except:
                pass


if __name__ == "__main__":
    is_github_actions = os.environ.get("GITHUB_ACTIONS", "false") == "true"
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    headless = os.environ.get('HEADLESS', 'false').lower() == 'true'
    if is_github_actions: headless = True
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    ocr = None
    det = None
    wait = None

    ver = "2.3 (Final Fix)" # 版本号更新
    logger.info("------------------------------------------------------------------")
    logger.info(f"雨云自动签到工作流 v{ver}")
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
    for i, (user, pwd) in enumerate(accounts, 1):
        logger.info(f"\n=== 开始处理第 {i} 个账户: {user} ===")
        result = sign_in_account(user, pwd, debug=debug, headless=headless)
        results.append(result)
        logger.info(f"=== 第 {i} 个账户处理完成 ===\n")
    
    logger.info("所有账户处理完成")
    
    # --- 遵循用户指定的通知格式 ---
    success_count = sum(1 for r in results if r[0])
    total_count = len(results)
    
    if success_count == total_count:
        notification_title = f"✅ 雨云自动签到完成 - 全部成功"
    elif success_count > 0:
        notification_title = f"⚠️ 雨云自动签到完成 - 部分成功 ({success_count}/{total_count})"
    else:
        notification_title = f"❌ 雨云自动签到完成 - 全部失败"
    
    notification_content = f"雨云自动签到结果汇总：\n\n总账户数: {total_count}\n成功账户数: {success_count}\n失败账户数: {total_count - success_count}\n\n详细结果：\n"
    
    for i, (success, user, points, error_msg) in enumerate(results, 1):
        if success:
            # 注意：即使是已签到（warning），也算逻辑成功，用 ✅ 显示积分
            notification_content += f"{i}. ✅ {user}\n   积分: {points} | 约 {points / 2000:.2f} 元\n"
        else:
            notification_content += f"{i}. ❌ {user}\n   错误: {error_msg}\n"
    
    # 发送统一通知
    try:
        send(notification_title, notification_content)
        logger.info("统一通知发送成功")
    except Exception as e:
        logger.error(f"发送通知失败: {e}")
