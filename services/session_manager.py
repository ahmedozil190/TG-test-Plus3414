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
        "lang_code": "en" # Forces Telegram messages/OTPs to English
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
            await asyncio.sleep(random.uniform(1.0, 2.5))
            me = await client.get_me()
            
            # 1. API Level Check
            if me.is_scam or me.is_fake or me.is_restricted:
                error_to_raise = "This account is restricted or frozen by Telegram."
            
            # 2. Strict Physical Check (Saved Messages)
            if not error_to_raise:
                try:
                    await asyncio.sleep(1.0)
                    test_msg = await client.send_message("me", "System test")
                    await test_msg.delete()
                except Exception as e:
                    # IF IT FAILS TO MESSAGE ITSELF, THE ACCOUNT IS DEAD OR BANNED. DO NOT PASS!
                    error_to_raise = f"This account is completely frozen/banned. ({type(e).__name__})"
                    
            # 3. Smart SpamBot Test (Language-Agnostic)
            if not error_to_raise:
                try:
                    import time
                    start_time = time.time()
                    target_bot = 178220800 # SpamBot ID
                    
                    await asyncio.sleep(random.uniform(1.5, 2.5))
                    await client.send_message(target_bot, "/start")
                    
                    spambot_replied = False
                    for i in range(20): # Wait up to 10 seconds
                        await asyncio.sleep(0.5)
                        async for msg in client.get_chat_history(target_bot, limit=3):
                            if msg.from_user and msg.from_user.id == target_bot and msg.date.timestamp() > (start_time - 2):
                                text = (msg.text or "").lower()
                                spambot_replied = True
                                
                                # Comprehensive restriction keywords (English, Arabic, Russian)
                                negatives = [
                                    # English
                                    "unfortunately", "limited", "restrictions", "restricted",
                                    "can't message", "cannot message", "can not message",
                                    "only send messages to mutual", "only message people",
                                    "spam", "banned", "suspended", "violated",
                                    "your account is limited", "temporarily limited",
                                    # Arabic
                                    "للاسف", "للأسف", "قيود", "مقيد", "محظور", "محدود", "مؤقت",
                                    # Russian  
                                    "к сожалению", "ограничен", "спам"
                                ]
                                
                                if any(word in text for word in negatives):
                                    error_to_raise = "This account is spam-restricted/limited from messaging."
                                elif msg.reply_markup:
                                    # All localized restriction messages have 'Appeal/More Info' buttons. Clean accounts don't!
                                    error_to_raise = "This account is spam-restricted (Appeal buttons active)."
                                break # Processed
                        if spambot_replied:
                            break
                    
                    # If SpamBot never replied in 10s, that itself is suspicious
                    if not spambot_replied:
                        logging.warning("SpamBot did not reply within timeout — treating as suspicious.")
                            
                except Exception as e:
                    # If we can't send a message to a bot, it's a high signal of a restricted account
                    err_type = type(e).__name__
                    if any(x in err_type for x in ["PeerFlood", "UserRestricted", "Forbidden", "ChatWriteForbidden"]):
                        error_to_raise = f"This account is messaging-restricted/spam-blocked. ({err_type})"
                    elif any(x in err_type for x in ["Unauthorized", "UserDeactivated"]):
                        error_to_raise = f"Session revoked by Telegram. ({err_type})"
                    else:
                        logging.warning(f"Unexpected SpamBot check error: {e}")

        except Exception as e:
            logging.error(f"Internal Health Check Error: {e}")
            if not error_to_raise:
                error_to_raise = f"Account session revoked or frozen. ({type(e).__name__})"

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

async def get_telegram_login_code(session_string: str, after_ts: float = None) -> str | None:
    import time
    client = await create_client(session_string)
    code = None
    now = time.time()
    
    try:
        await client.connect()
        async for message in client.get_chat_history(777000, limit=5):
            msg_ts = message.date.timestamp() if message.date else 0
            
            # 1. Use after_ts if provided (Purchase time)
            if after_ts and msg_ts < after_ts:
                continue
                
            # 2. Fallback to 120s window if no after_ts
            if not after_ts and (now - msg_ts) > 120:
                continue

            text = message.text
            if not text:
                continue
            
            # The code is usually a 5-digit number, often with "Login code:" context
            # We look for the most recent one that matches the pattern
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

async def is_session_alive(session_string: str) -> bool:
    try:
        client = await create_client(session_string)
        await client.connect()
        me = await client.get_me()
        if not me or me.is_scam or me.is_fake or me.is_restricted:
            return False
        
        # Check SpamBot instead of 'me' for real messaging capability
        target_bot = 178220800
        try:
            await client.send_message(target_bot, "/start")
            # If we sent successfully, the account can message bots (not completely restricted)
            return True
        except Exception as e:
            err_type = type(e).__name__
            if any(x in err_type for x in ["PeerFlood", "UserRestricted", "Forbidden", "ChatWriteForbidden"]):
                return False # Messaging restricted
            # If it's a different error (like Timeout), we might still consider it alive if me.id exists
            # but usually for a sourcing bot, if it can't message SpamBot, it's useless.
            return False
            
    except Exception as e:
        logging.warning(f"Session failed alive check: {e}")
        return False
    finally:
        try:
            if 'client' in locals() and client.is_connected:
                await client.disconnect()
        except:
            pass
