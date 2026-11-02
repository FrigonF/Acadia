import os
import time
from playwright.sync_api import sync_playwright

os.makedirs('qa_screenshots', exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})

    print("1. Navigating to ACADIA at http://localhost:5173 ...")
    page.goto('http://localhost:5173')
    page.wait_for_load_state('networkidle')
    time.sleep(1)

    # 1. Login Modal
    print("Capturing 01_login_modal.png")
    page.screenshot(path='qa_screenshots/01_login_modal.png')

    # Click authorize button
    page.click('button:has-text("Authorize & Enter Console")')
    time.sleep(1.5)
    page.wait_for_load_state('networkidle')

    # 2. Overview Screen
    print("Capturing 02_overview.png")
    page.screenshot(path='qa_screenshots/02_overview.png')

    # 3. Institutions Screen
    page.click('button:has-text("Institutions")')
    time.sleep(1)
    print("Capturing 03_institutions.png")
    page.screenshot(path='qa_screenshots/03_institutions.png')

    # 4. Student Directory Screen
    page.click('button:has-text("Student directory")')
    time.sleep(1)
    print("Capturing 04_students.png")
    page.screenshot(path='qa_screenshots/04_students.png')

    # Open Add Student Modal
    page.click('button:has-text("+ Add Student")')
    time.sleep(0.5)
    print("Capturing 04b_add_student_modal.png")
    page.screenshot(path='qa_screenshots/04b_add_student_modal.png')
    page.click('button:has-text("Cancel")')
    time.sleep(0.5)

    # 5. Data Intake Screen
    page.click('button:has-text("Data intake")')
    time.sleep(1)
    print("Capturing 05_data_intake.png")
    page.screenshot(path='qa_screenshots/05_data_intake.png')

    # 6. Verification Queue Screen
    page.click('button:has-text("Verification queue")')
    time.sleep(1)
    print("Capturing 06_verification_queue.png")
    page.screenshot(path='qa_screenshots/06_verification_queue.png')

    # 7. Record Integrity Screen
    page.click('button:has-text("Record integrity")')
    time.sleep(1)
    print("Capturing 07_record_integrity.png")
    page.screenshot(path='qa_screenshots/07_record_integrity.png')

    # 8. Reports & Audit Screen
    page.click('button:has-text("Reports & audit")')
    time.sleep(1)
    print("Capturing 08_reports_and_audit.png")
    page.screenshot(path='qa_screenshots/08_reports_and_audit.png')

    # 9. Tablet Viewport (768x1024)
    print("Testing Tablet Viewport (768x1024)...")
    page.set_viewport_size({'width': 768, 'height': 1024})
    time.sleep(1)
    page.click('button:has-text("Overview")')
    time.sleep(1)
    print("Capturing 09_overview_tablet.png")
    page.screenshot(path='qa_screenshots/09_overview_tablet.png')

    browser.close()
    print("=== BROWSER QA SCREENSHOTS COMPLETED SUCCESSFULLY ===")
