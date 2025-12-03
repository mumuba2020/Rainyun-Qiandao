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
                    
                    # 使用 XPath 定位“每日签到”卡片和操作按钮
                    # 尝试定位“每日签到”卡片本身
                    sign_card_xpath = '//div[contains(@class, "card-header-collapsed") and contains(., "每日签到")]'
                    sign_card = wait.until(EC.presence_of_element_located((By.XPATH, sign_card_xpath)))

                    # 在卡片内寻找“领奖励”或“签到”按钮
                    # 注意：领奖励按钮是 primary 且带有 'btn-relief' class
                    sign_button_xpath = sign_card_xpath + '/following-sibling::div//button[contains(@class, "btn-relief-primary")]'
                    sign_button = wait.until(EC.element_to_be_clickable((By.XPATH, sign_button_xpath)))
                    
                    # 检查按钮文本是否是“领奖励”或“签到”
                    button_text = sign_button.get_attribute("textContent").strip()
                    
                    if "领奖励" in button_text or "签到" in button_text:
                        # 滚动到元素位置并点击
                        driver.execute_script("arguments[0].scrollIntoView(true);", sign_button)
                        time.sleep(1)
                        logger.info(f"找到并点击每日签到按钮: {button_text}")
                        driver.execute_script("arguments[0].click();", sign_button)
                        
                        # 处理可能出现的二次验证码
                        try:
                            logger.info("检查是否需要二次验证码")
                            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "tcaptcha_iframe_dy")))
                            logger.info("处理二次验证码")
                            # 需要确保 process_captcha 函数中可以访问全局的 ocr/det/wait
                            process_captcha() 
                            driver.switch_to.default_content()
                        except TimeoutException:
                            logger.info("未触发二次验证码或验证码框架加载失败")
                            driver.switch_to.default_content()
                        
                        logger.info("签到操作完成，等待积分刷新...")
                        sign_in_completed = True
                        time.sleep(5) # 留出时间让服务器处理和页面刷新
                        break
                    else:
                        logger.info(f"按钮文本为 '{button_text}'，可能已签到。")
                        sign_in_completed = True
                        break # 如果按钮不是签到/领奖励，则认为已完成
                        
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
            
            if initial_points > 0 and current_points > initial_points:
                added_points = current_points - initial_points
                logger.info(f"✅ 任务执行成功！积分已增加 {added_points} 点。")
                logger.info(f"当前剩余积分: {current_points} | 约为 {current_points / 2000:.2f} 元")
                return True, user, current_points, None
                
            elif current_points > 0 and (initial_points > 0 and current_points == initial_points):
                logger.warning(f"⚠️ 当前剩余积分: {current_points} (与签到前积分相同: {initial_points})")
                logger.info("任务执行完毕，但积分未增加，可能已签到。")
                # 流程已执行，标记为成功，但给出警告信息
                return True, user, current_points, "积分未增加，可能已签到。"
                
            else:
                # 可能是 initial_points 为 0，无法比较，但 current_points 成功获取，默认视为流程成功
                logger.info(f"当前剩余积分: {current_points} | 约为 {current_points / 2000:.2f} 元")
                logger.info("任务执行成功！") 
                return True, user, current_points, None
                
        else:
            logger.error("❌ 登录失败！")
            return False, user, 0, "登录失败，未能进入仪表盘页面，请检查账号密码或验证码处理逻辑。"

    except Exception as e:
        err_msg = f"脚本运行期间发生致命异常: {str(e)}"
        logger.error(err_msg, exc_info=True)
        return False, user, 0, err_msg
