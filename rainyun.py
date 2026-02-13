import logging
import os
import random
import re
import time

import cv2
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

import ICR

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

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

try:
    from notify import send
    print("已加载通知模块 (notify.py)")
except ImportError:
    print("警告: 未找到 notify.py，将无法发送通知。")
    def send(*args, **kwargs):
        pass


def init_selenium(debug=False, headless=False) -> WebDriver:
    ops = Options()
    if headless or os.environ.get("GITHUB_ACTIONS", "false") == "true":
        for option in ['--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu',
                       '--disable-extensions', '--disable-software-rasterizer',
                       '--remote-debugging-port=9222', '--disable-background-timer-throttling',
                       '--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding',
                       '--disable-features=VizDisplayCompositor',
                       '--disable-ipc-flooding-protection',
                       '--disable-default-apps']:
            ops.add_argument(option)
    ops.add_argument('--window-size=1920,1080')
    ops.add_argument('--disable-blink-features=AutomationControlled')
    ops.add_argument('--no-proxy-server')
    ops.add_argument('--lang=zh-CN')
    
    is_github_actions = os.environ.get("GITHUB_ACTIONS", "false") == "true"
    if debug and not is_github_actions:
        ops.add_experimental_option("detach", True)
    
    try:
        if ChromeDriverManager:
            if ChromeType and hasattr(ChromeType, 'GOOGLE'):
                manager = ChromeDriverManager(chrome_type=ChromeType.GOOGLE)
            else:
                manager = ChromeDriverManager()
            driver_path = manager.install()
            if os.path.isfile(driver_path) and os.access(driver_path, os.X_OK):
                service = Service(driver_path)
                driver = webdriver.Chrome(service=service, options=ops)
                return driver
            else:
                driver_dir = os.path.dirname(driver_path)
                for root, dirs, files in os.walk(driver_dir):
                    for file in files:
                        if file in ['chromedriver', 'chromedriver.exe']:
                            correct_path = os.path.join(root, file)
                            if os.access(correct_path, os.X_OK):
                                service = Service(correct_path)
                                driver = webdriver.Chrome(service=service, options=ops)
                                return driver
    except Exception as e:
        print(f"webdriver-manager失败: {e}")

    try:
        driver = webdriver.Chrome(options=ops)
        return driver
    except Exception:
        pass
        
    raise Exception("无法初始化Selenium WebDriver")


def download_image(url, filename):
    os.makedirs("temp", exist_ok=True)
    try:
        response = requests.get(url, timeout=10, proxies={"http": None, "https": None}, verify=False)
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


def process_captcha(driver, wait):
    try:
        download_captcha_img(driver, wait)
        logger.info("开始识别验证码")
        captcha = cv2.imread("temp/captcha.jpg")
        result = ICR.main("temp/captcha.jpg", "temp/sprite.jpg")
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
        reload = driver.find_element(By.XPATH, '//*[@id="reload"]')
        time.sleep(5)
        reload.click()
        time.sleep(5)
        process_captcha(driver, wait)
    except TimeoutException:
        logger.error("获取验证码图片失败")


def download_captcha_img(driver, wait):
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


def sign_in_account(user, pwd, debug=False, headless=False):
    timeout = 30
    driver = None
    
    try:
        logger.info(f"开始处理账户: {user}")
        if not debug:
            time.sleep(random.randint(5, 10))
        
        logger.info("初始化 Selenium")
        driver = init_selenium(debug=debug, headless=headless)
        
        try:
            with open("stealth.min.js", mode="r") as f: js = f.read()
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": js})
        except: pass
        
        logger.info("发起登录请求")
        driver.get("https://app.rainyun.com/auth/login")
        logger.info(f"当前页面URL: {driver.current_url}")
        logger.info(f"页面标题: {driver.title}")
        
        time.sleep(5)
        
        wait = WebDriverWait(driver, timeout)
        
        try:
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            logger.info("页面加载完成")
        except:
            logger.warning("页面加载超时，继续尝试查找元素")
        
        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return typeof Vue !== 'undefined'") or len(d.find_elements(By.TAG_NAME, "input")) > 0
            )
            logger.info("JavaScript 框架已加载或找到输入元素")
        except:
            logger.warning("等待 JavaScript 框架超时")
        
        try:
            username = wait.until(EC.visibility_of_element_located((By.NAME, 'login-field')))
            logger.info("找到用户名输入框")
        except TimeoutException:
            logger.error("未找到用户名输入框，页面可能未正确加载")
            logger.info(f"页面源码长度: {len(driver.page_source)}")
            
            all_inputs = driver.find_elements(By.TAG_NAME, "input")
            logger.info(f"页面中找到 {len(all_inputs)} 个 input 元素")
            for i, inp in enumerate(all_inputs[:5]):
                logger.info(f"  Input {i}: name={inp.get_attribute('name')}, type={inp.get_attribute('type')}, placeholder={inp.get_attribute('placeholder')}")
            
            logger.info("尝试其他选择器...")
            
            try:
                username = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[type="text"]')))
                logger.info("通过 CSS 选择器找到输入框")
            except:
                try:
                    username = wait.until(EC.visibility_of_element_located((By.XPATH, '//input[contains(@placeholder, "账号") or contains(@placeholder, "用户名") or contains(@placeholder, "手机") or contains(@placeholder, "邮箱")]')))
                    logger.info("通过 XPath 找到输入框")
                except:
                    raise TimeoutException("无法找到登录输入框")
        
        password = wait.until(EC.visibility_of_element_located((By.NAME, 'login-password')))
        try:
            login_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="app"]/div[1]/div[1]/div/div[2]/fade/div/div/span/form/button')))
        except:
            login_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]')))
            
        username.clear()
        password.clear()
        username.send_keys(user)
        time.sleep(0.5)
        password.send_keys(pwd)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", login_button)
        
        try:
            wait.until(EC.visibility_of_element_located((By.ID, 'tcaptcha_iframe_dy')))
            logger.warning("触发验证码！")
            driver.switch_to.frame("tcaptcha_iframe_dy")
            process_captcha(driver, wait)
        except TimeoutException:
            logger.info("未触发验证码")
        
        time.sleep(5)
        driver.switch_to.default_content()
        
        if "dashboard" in driver.current_url:
            logger.info("登录成功！")
            logger.info("正在转到赚取积分页")
            
            for _ in range(3):
                try:
                    driver.get("https://app.rainyun.com/account/reward/earn")
                    wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                    time.sleep(3)

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
                        
                        logger.info("等待验证码加载（如果有）...")
                        
                        try:
                            WebDriverWait(driver, 15, poll_frequency=0.25).until(
                                EC.visibility_of_element_located((By.ID, "tcaptcha_iframe_dy"))
                            )
                            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "tcaptcha_iframe_dy")))
                            logger.info("处理验证码")
                            process_captcha(driver, wait)
                            driver.switch_to.default_content()
                        except TimeoutException:
                            logger.info("未触发验证码，继续")
                            driver.switch_to.default_content()
                        except Exception as e:
                            logger.error(f"验证码处理过程出错: {e}")
                            driver.switch_to.default_content()
                        
                        logger.info("赚取积分操作完成")
                        break
                    else:
                        driver.refresh()
                        time.sleep(3)
                except Exception as e:
                    logger.error(f"出错: {e}")
                    time.sleep(3)
            
            driver.implicitly_wait(5)
            try:
                points_raw = driver.find_element(By.XPATH, '//*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[1]/div[1]/div/p/div/h3').get_attribute("textContent")
                current_points = int(''.join(re.findall(r'\d+', points_raw)))
                logger.info(f"当前剩余积分: {current_points} | 约为 {current_points / 2000:.2f} 元")
            except:
                current_points = 0
                
            logger.info("任务执行成功！")
            return True, user, current_points, None
        else:
            return False, user, 0, "登录失败"

    except Exception as e:
        logger.error(f"异常: {str(e)}", exc_info=True)
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
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    ver = "2.3"
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
            notification_content += f"{i}. ✅ {user}\n   积分: {points} | 约 {points / 2000:.2f} 元\n"
        else:
            notification_content += f"{i}. ❌ {user}\n   错误: {error_msg}\n"
    
    try:
        send(notification_title, notification_content)
        logger.info("统一通知发送成功")
    except Exception as e:
        logger.error(f"发送通知失败: {e}")
