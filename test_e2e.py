import pytest
import json
from playwright.sync_api import Page, expect
import re

# -------------------- HELPERS --------------------
def admin_login(page: Page, live_server: str):
    """Helper to perform admin login."""
    page.goto(live_server)
    # Triple-click the name element
    name_selector = '#p-name'
    page.click(name_selector, click_count=3)
    # Fill password and login
    page.fill('#pass', 'Alwande.m18')
    page.click('button:has-text("Login")')
    # Wait for admin mode to be active
    page.wait_for_selector('body.admin-mode', state='attached')

# -------------------- TESTS --------------------
def test_home_page_loads(page: Page, live_server: str):
    page.goto(live_server)
    expect(page).to_have_title(re.compile(r"Alwande Mbonambi's Portfolio|Portfolio"))
    expect(page.locator('#p-name')).to_be_visible()

def test_admin_login_and_ui_change(page: Page, live_server: str):
    """Triple‑click, login, verify admin elements appear."""
    page.goto(live_server)
    name_el = page.locator('#p-name')
    name_el.click(click_count=3)
    page.fill('#pass', 'Alwande.m18')
    page.click('button:has-text("Login")')
    page.wait_for_selector('body.admin-mode', state='attached')
    # Admin buttons should be visible
    expect(page.locator('#save-btn')).to_be_visible()
    expect(page.locator('#logout-btn')).to_be_visible()
    # "Chatbot" nav link should appear (admin-only)
    expect(page.locator('a:has-text("Chatbot")')).to_be_visible()

def test_logout_removes_admin_mode(page: Page, live_server: str):
    admin_login(page, live_server)
    page.click('#logout-btn')
    # Admin mode should disappear
    page.wait_for_selector('body.admin-mode', state='detached')
    expect(page.locator('#save-btn')).not_to_be_visible()
    expect(page.locator('a:has-text("Chatbot")')).not_to_be_visible()

def test_edit_contact_info_persists(page: Page, live_server: str):
    """Edit email/phone in admin mode, save, reload, verify persistence."""
    admin_login(page, live_server)
    # Admin email input becomes visible
    email_input = page.locator('#edit-email')
    email_input.fill('e2e@test.com')
    phone_input = page.locator('#edit-phone')
    phone_input.fill('+999999999')
    # Click SYNC DATA and accept alert
    page.on('dialog', lambda dialog: dialog.accept())
    page.click('#save-btn')
    # Wait for alert to close (approx)
    page.wait_for_timeout(500)
    # Reload page and re-login to see persisted data
    page.reload()
    admin_login(page, live_server)
    # Check that displayed email/phone updated
    expect(page.locator('#contact-email')).to_have_text('e2e@test.com')
    expect(page.locator('#contact-phone')).to_have_text('+999999999')

def test_add_qualification(page: Page, live_server: str):
    admin_login(page, live_server)
    # Click "+ Add Qualification"
    page.click('#qual button:has-text("Add Qualification")')
    # New card should appear with default fields
    new_card = page.locator('#qual-list .card').last
    # Edit the qualification name (admin input inside card)
    name_input = new_card.locator('input[placeholder="Deg Name"]')
    name_input.fill('Test Degree')
    # Add a module
    module_input = new_card.locator('input[placeholder="Module"]')
    module_input.fill('Test Module')
    grade_input = new_card.locator('input[placeholder="%"]')
    grade_input.fill('85')
    new_card.locator('button:has-text("+")').click()
    # Module should appear
    expect(new_card.locator('span:has-text("Test Module (85%)")')).to_be_visible()
    # Save and verify persistence
    page.on('dialog', lambda dialog: dialog.accept())
    page.click('#save-btn')
    page.wait_for_timeout(500)
    page.reload()
    admin_login(page, live_server)
    expect(page.locator('#qual-list .card').last.locator('h3')).to_have_text('Test Degree')

def test_upload_profile_image(page: Page, live_server: str):
    admin_login(page, live_server)
    # Locate file input for profile picture
    file_input = page.locator('.profile-container input[type="file"]')
    # Simulate file upload (create a dummy image file)
    file_input.set_input_files('tests/dummy.jpg')  # you must have a dummy.jpg in tests/ folder
    # Wait for upload to complete (alert appears)
    page.on('dialog', lambda dialog: dialog.accept())
    page.wait_for_timeout(2000)
    # Profile image should have changed (src contains cloudinary URL)
    profile_img = page.locator('#p-img')
    src = profile_img.get_attribute('src')
    assert 'cloudinary' in src or 'mock' in src  # depending on mocking

def test_upload_cv_pdf(page: Page, live_server: str):
    admin_login(page, live_server)
    # CV upload input is inside the home section
    cv_input = page.locator('#home input[type="file"]')
    cv_input.set_input_files('tests/dummy.pdf')
    page.on('dialog', lambda dialog: dialog.accept())
    page.wait_for_timeout(2000)
    # "View CV" button should appear
    expect(page.locator('#cv-btn')).to_be_visible()

def test_chatbot_interaction(page: Page, live_server: str):
    """Open chat, send message, receive reply (mocked in backend)."""
    page.goto(live_server)
    # Click chatbot icon
    page.click('.chatbot-icon')
    # Wait for chat window to be visible
    page.wait_for_selector('.chatbot-window', state='visible')
    # Type question
    page.fill('#chat-input', 'What skills do you have?')
    page.click('#send-chat')
    # Wait for bot reply bubble
    bot_reply = page.locator('.chatbot-messages .bot .bubble').last
    expect(bot_reply).to_be_visible()
    # Assert something (depending on mocked response)
    reply_text = bot_reply.inner_text()
    assert len(reply_text) > 0

def test_mobile_menu(page: Page, live_server: str):
    """Simulate mobile viewport and check hamburger menu."""
    page.set_viewport_size({'width': 375, 'height': 667})  # iPhone SE size
    page.goto(live_server)
    # Hamburger button should be visible
    menu_btn = page.locator('.mobile-menu-btn')
    expect(menu_btn).to_be_visible()
    # Menu links are initially hidden
    nav_right = page.locator('.nav-right')
    expect(nav_right).not_to_be_visible()
    menu_btn.click()
    expect(nav_right).to_be_visible()
    # Click a link should close menu (optional)
    nav_right.locator('a:has-text("Home")').click()
    # After navigation, menu may collapse; we can check URL
    expect(page).to_have_url(live_server + '#home')

def test_ai_knowledge_upload(page: Page, live_server: str):
    admin_login(page, live_server)
    # Scroll to AI Extra Knowledge section
    page.locator('#ai-knowledge').scroll_into_view_if_needed()
    # Type text into textarea
    knowledge_textarea = page.locator('#extra-knowledge')
    knowledge_textarea.fill('I love hiking and coding.')
    # Click SYNC DATA
    page.on('dialog', lambda dialog: dialog.accept())
    page.click('#save-btn')
    page.wait_for_timeout(500)
    # Reload and verify textarea retains value
    page.reload()
    admin_login(page, live_server)
    expect(page.locator('#extra-knowledge')).to_have_value('I love hiking and coding.')

def test_upload_knowledge_file(page: Page, live_server: str):
    admin_login(page, live_server)
    page.locator('#ai-knowledge').scroll_into_view_if_needed()
    file_input = page.locator('#knowledge-file')
    file_input.set_input_files('tests/knowledge.txt')
    # Click "Upload & Add" button
    page.click('button:has-text("Upload & Add")')
    page.on('dialog', lambda dialog: dialog.accept())
    page.wait_for_timeout(2000)
    # The textarea should now contain the file content
    # (depending on implementation, it appends; we can check length)
    textarea_val = page.locator('#extra-knowledge').input_value()
    assert len(textarea_val) > 0

def test_chatbot_uses_extra_knowledge(page: Page, live_server: str):
    """After adding extra knowledge, chatbot should reflect it."""
    admin_login(page, live_server)
    # Add knowledge
    page.locator('#extra-knowledge').fill('My favorite color is blue.')
    page.on('dialog', lambda dialog: dialog.accept())
    page.click('#save-btn')
    page.wait_for_timeout(500)
    # Test chatbot
    page.click('.chatbot-icon')
    page.fill('#chat-input', 'What is my favorite color?')
    page.click('#send-chat')
    bot_reply = page.locator('.chatbot-messages .bot .bubble').last
    expect(bot_reply).to_contain_text('blue')