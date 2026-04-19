import re
import random
import logging
import asyncio
from pyrogram import Client, errors
from pyrogram.raw import functions, types
from typing import Dict

from config import API_ID, API_HASH

# We store temporary clients here during the sign-in flow
login_clients: Dict[int, Client] = {}

async def create_client(session_string: str = None) -> Client:
    # Use professional identity strings to avoid automated session bans
    identity = {
        "device_model": "Samsung SM-S918B", # Galaxy S23 Ultra
        "system_version": "Android 14", # Modern Android version
        "app_version": "10.14.5", # Recent Telegram version
        "lang_code": "en"
    }
    if session_string:
        client = Client(name="temp", api_id=API_ID, api_hash=API_HASH, session_string=session_string, in_memory=True, **identity)
    else:
        client = Client(name="temp", api_id=API_ID, api_hash=API_HASH, in_memory=True, **identity)
    return client

async def request_app_code(user_id: int, phone_number: str) -> str:
    """Returns phone_code_hash"""
    client = await create_client()
    await client.connect()
    await asyncio.sleep(1.5) # Human-like delay after connection
    
    try:
        sent_code = await client.send_code(phone_number)
        login_clients[user_id] = client # Store client so we can complete sign_in later
        return sent_code.phone_code_hash
    except errors.PhoneNumberBanned:
        raise Exception("This phone number is banned from Telegram.")
    except errors.UserDeactivated:
        raise Exception("This account is frozen by Telegram.")
    except Exception as e:
        if client.is_connected:
            await client.disconnect()
        raise e

async def submit_app_code(user_id: int, phone_number: str, phone_code_hash: str, phone_code: str) -> str | None:
    """Returns session_string if successful"""
    client = login_clients.get(user_id)
    if not client:
        logging.error(f"Submit OTP Failed: No active client found in memory for user {user_id}. This usually means the server restarted or hit a different Railway instance.")
        return None
        
    try:
        # Human-like delay before sign-in (simulate typing OTP)
        await asyncio.sleep(random.uniform(2.5, 5.5)) 
        await client.sign_in(phone_number, phone_code_hash, phone_code)
        
        # Health Check: Deep inspection after login
        error_to_raise = None
        try:
            # Random delay before checking user info to be safe
            await asyncio.sleep(random.uniform(1.0, 2.5))
            me = await client.get_me()
            
            # 1. Check for Scam/Fake/Restricted flags in User Object
            if me.is_scam or me.is_fake or me.is_restricted:
                if me.is_restricted:
                    error_to_raise = "This account is restricted or spam-blocked."
                else:
                    error_to_raise = "This account is frozen by Telegram."
            
            # 2. Saved Messages Test (Physical Test)
            # Ensures the account is not completely frozen/deactivated from Telegram's end
            if not error_to_raise:
                try:
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    test_msg = await client.send_message("me", "/start")
                    await test_msg.delete()
                except (errors.UserDeactivated, errors.UserDeactivatedBan, errors.UserBannedInChannel):
                    error_to_raise = "This account is completely frozen/banned by Telegram."
                except Exception as e:
                    pass # Ignore minor network errors to avoid false positive logouts
                    
            # 3. Smart SpamBot Test
            # Messages SpamBot but ONLY fails if SpamBot explicitly tells us the account is restricted.
            if not error_to_raise:
                try:
                    import time
                    start_time = time.time()
                    target_bot = 178220800 # SpamBot ID
                    
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                    await client.send_message(target_bot, "/start")
                    
                    spambot_responded = False
                    for i in range(12): # Wait up to 6 seconds for reply
                        await asyncio.sleep(0.5)
                        async for msg in client.get_chat_history(target_bot, limit=2):
                            if msg.from_user and msg.from_user.id == target_bot and msg.date.timestamp() > (start_time - 1):
                                spambot_responded = True
                                text = (msg.text or "").lower()
                                
                                # Arabic & English negative keywords indicating restrictions
                                negatives = ["unfortunately", "limited", "restrictions", "للاسف", "للأسف", "قيود", "مقيد"]
                                # Positive keywords
                                positives = ["good news", "birds", "أخبار جيدة", "اخبار جيدة", "لا توجد قيود"]
                                
                                if any(word in text for word in negatives):
                                    error_to_raise = "This account is spam-restricted (Cannot send to non-contacts)."
                                elif msg.reply_markup:
                                    error_to_raise = "This account is spam-restricted (Appeal buttons present)."
                                break # Message processed
                        if spambot_responded:
                            break
                            
                except Exception as e:
                    pass # Do not flag the account if Spambot check fails for any environmental reason
                    
        except Exception as e:
            logging.error(f"Internal Health Check Error: {e}")
            if not error_to_raise:
                error_to_raise = "Error verifying account status. Please try again."

        if error_to_raise:
            try: await client.log_out()
            except: pass
            raise Exception(error_to_raise)

        session_string = await client.export_session_string()
        return session_string
    except Exception as e:
        # Final pass-through for anticipated exceptions
        err_msg = str(e).lower()
        if any(msg in err_msg for msg in ["restricted", "spam-blocked", "frozen", "security check", "responding", "deactivated"]):
            raise e
        raise e
    finally:
        try:
            if client and client.is_connected:
                await client.disconnect()
        except:
            pass # Client might already be terminated by log_out()
        login_clients.pop(user_id, None)

async def get_telegram_login_code(session_string: str) -> str | None:
    client = await create_client(session_string)
    code = None
    
    try:
        await client.connect()
        async for message in client.get_chat_history(777000, limit=3):
            text = message.text
            if not text:
                continue
            
            # The code is usually a 5-digit number
            match = re.search(r'\b(\d{5})\b', text)
            if match:
                code = match.group(1)
                break
    except Exception as e:
        logging.error(f"Error fetching code for session: {e}")
    finally:
        if client.is_connected:
            await client.disconnect()
            
    return code
