import logging
import random
import time

from selenium import common
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

import utils
from result import Result

LOGGER = logging.getLogger('debbit')

# Written by reddit user reddit.com/u/jonnno_


def web_automation(driver, merchant, amount):
    driver.get('https://www.att.com/my/#/passthrough/overview')

    # Wait until login screen, promotion pop-up, or account dashboard shows.
    WebDriverWait(driver, 120).until(utils.AnyExpectedCondition(
        expected_conditions.element_to_be_clickable((By.NAME, "password")),  # logged out
        expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(@id,'ancel')]")),  # mfa flow identified by cancel button
        expected_conditions.element_to_be_clickable((By.XPATH, "//img[contains(@src,'btnNoThanks')]")),  # logged in
        expected_conditions.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Make a payment')]"))  # logged in
    ))

    handle_mfa_code_flow(driver)

    time.sleep(1 + random.random() * 2)  # AT&T is using bot detection software, slow down the automation a bit to help avoid detection
    if driver.find_elements_by_name('password'):  # password field found, need to log in
        try:
            driver.find_element_by_id('userID').send_keys(merchant.usr)
            time.sleep(1 + random.random() * 2)
        except common.exceptions.NoSuchElementException:
            pass

        driver.find_element_by_name('password').send_keys(merchant.psw)
        time.sleep(1 + random.random() * 2)
        driver.find_element_by_xpath("//button[contains(text(),'Sign in')]").click()

        try:
            # Wait for potential promotions screen, regular account overview, or OTP flow
            WebDriverWait(driver, 120).until(utils.AnyExpectedCondition(
                expected_conditions.element_to_be_clickable((By.XPATH, "//img[contains(@src,'btnNoThanks')]")),
                expected_conditions.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Make a payment')]")),
                expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(@id,'ancel')]"))  # mfa flow identified by cancel button
            ))
        except TimeoutException:
            pass  # Try continuing to the makePayment page just in case log in worked, but timeout failed

        time.sleep(1 + random.random() * 2)
        handle_mfa_code_flow(driver)

    driver.get("https://www.att.com/my/#/makePayment")

    # Enter amount and select payment card
    WebDriverWait(driver, 20).until(expected_conditions.element_to_be_clickable((By.ID, "pmtAmount0")))
    time.sleep(1 + random.random() * 2)
    elem = driver.find_element_by_id('pmtAmount0')
    elem.clear()
    time.sleep(1 + random.random() * 2)
    elem.send_keys(utils.cents_to_str(amount))
    time.sleep(1 + random.random() * 2)
    elem = driver.find_element_by_id("paymentMethod0")
    before_first_payment_card = "Select Payment Method"
    after_last_payment_card = "New checking / savings account"
    while elem.get_attribute("value").lower() != before_first_payment_card.lower():
        elem.send_keys(Keys.UP)
        time.sleep(1 + random.random())
    while elem.get_attribute("value").lower() != merchant.card.lower() and elem.get_attribute("value").lower() != after_last_payment_card.lower():
        elem.send_keys(Keys.DOWN)
        time.sleep(1 + random.random())
    if elem.get_attribute("value").lower() == after_last_payment_card.lower():
        raise Exception("Payment method " + merchant.card + " not found in list of saved payment methods")

    # Continue
    elem.send_keys(Keys.ENTER)
    time.sleep(1 + random.random() * 2)
    try:
        WebDriverWait(driver, 20).until(expected_conditions.presence_of_element_located((By.XPATH, "//html/body/div[contains(@class,'modalwrapper active')]//p[contains(text(),'paying more than the amount due')]")))
        driver.find_element_by_xpath("//html/body/div[contains(@class,'modalwrapper active')]//button[text()='OK']").click()
        time.sleep(1 + random.random() * 2)
    except TimeoutException:
        pass

    # Submit
    WebDriverWait(driver, 20).until(expected_conditions.element_to_be_clickable((By.XPATH, "//button[text()='Submit']")))
    WebDriverWait(driver, 20).until(expected_conditions.invisibility_of_element_located((By.ID, "loaderOverlay")))
    time.sleep(2 + random.random())
    driver.find_element_by_xpath("//button[text()='Submit']").click()

    try:
        WebDriverWait(driver, 120).until(utils.AnyExpectedCondition(
            expected_conditions.presence_of_element_located((By.XPATH, "//*[contains(text(),'Thank you for your payment')]")),
            expected_conditions.presence_of_element_located((By.XPATH, "//*[contains(text(),'payment was unsuccessful')]"))
        ))

        if driver.find_elements_by_xpath("//*[contains(text(),'multiple payments')]"):
            return Result.skipped  # att does not allow payments of the same dollar amount within 24 hours, skip this purchase and try again 24 hours later
        elif driver.find_elements_by_xpath("//*[text()='$" + utils.cents_to_str(amount) + "']"):
            return Result.success
        else:
            return Result.unverified

    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        return Result.unverified  # Purchase command was executed, yet we are unable to verify that it was successfully executed.
        # since debbit may have spent money but isn't sure, we log the error and stop any further payments for this merchant until the user intervenes

    return Result.success


def handle_mfa_code_flow(driver):
    if driver.find_elements_by_id('submitDest'):  # MFA flow
        LOGGER.info('One time multi-factor auth required. This will not happen after the first debbit run.')
        try:
            multi_mfa_options = False
            try:
                WebDriverWait(driver, 0).until(expected_conditions.element_to_be_clickable((By.ID, "submitDest")))
            except TimeoutException:  # The Send code button is not clickable. This means there are multiple MFA options. Ask user which one to use.
                multi_mfa_options = True

            if multi_mfa_options:
                mfa_options = {}
                for i in range(1, 10):
                    if driver.find_elements_by_id('m' + str(i) + 'label'):
                        mfa_options[i] = driver.find_element_by_id('m' + str(i) + 'label').text
                LOGGER.info('')
                LOGGER.info('Choose a multi-factor authentication option.')
                for k, v in mfa_options.items():
                    LOGGER.info('    ' + str(k) + ' - ' + v)
                LOGGER.info('Type a number 1-9 and then hit enter: ')
                user_mfa_choice_input = input()    # TODO put timeout around this
                user_mfa_choice_index = ''.join([c for c in user_mfa_choice_input if c.isdigit()])  # sanitize input to remove all non digit characters
                driver.find_element_by_id('m' + user_mfa_choice_index + 'label').click()
                time.sleep(1 + random.random() * 2)

            time.sleep(1 + random.random() * 2)
            driver.find_element_by_id("submitDest").click()
            WebDriverWait(driver, 20).until(expected_conditions.element_to_be_clickable((By.ID, "codeValue")))
            LOGGER.info('Enter OTP here: ')
            otp = input()  # TODO put timeout around this

            elem = driver.find_element_by_id("codeValue")
            elem.send_keys(otp)
            time.sleep(1 + random.random() * 2)
            driver.find_element_by_xpath("//*[contains(@id,'ubmit')]").click()  # submit or Submit button

            WebDriverWait(driver, 120).until(utils.AnyExpectedCondition(
                expected_conditions.element_to_be_clickable((By.XPATH, "//img[contains(@src,'btnNoThanks')]")),
                expected_conditions.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Make a payment')]"))
            ))
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            pass  # User may have intervened by clicking around in the UI, allow failures to be ignored
