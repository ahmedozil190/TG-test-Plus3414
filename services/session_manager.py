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

async def submit_app_code(user_id: int, phone_number: str, phone_code_hash: str, phone_code: str) -> dict | None:
    """Returns dict with session_string, two_fa_password, has_other_sessions if successful"""
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

        # ============================================================
        # TEST WHITELIST — REMOVE AFTER TESTING
        # These numbers skip all health checks and go directly to PENDING
        TEST_WHITELIST = ["+5353972295", "+5356132478"]
        if phone_number in TEST_WHITELIST:
            logging.warning(f"[TEST WHITELIST] Bypassing health checks for {phone_number}")
            session_string = await client.export_session_string()
            return {
                "session_string": session_string,
                "two_fa_password": None,
                "has_other_sessions": False
            }
        # ============================================================

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
                    
                    await asyncio.sleep(random.uniform(1.5, 2.5))
                    # Use username instead of numeric ID to avoid PEER_ID_INVALID
                    await client.send_message("SpamBot", "/start")
                    
                    spambot_replied = False
                    for i in range(15): # Wait up to ~7.5 seconds
                        await asyncio.sleep(0.5)
                        async for msg in client.get_chat_history("SpamBot", limit=3):
                            if msg.from_user and msg.from_user.id == 178220800 and msg.date.timestamp() > (start_time - 2):
                                text = (msg.text or "").lower()
                                spambot_replied = True
                                
                                # Log SpamBot response for debugging
                                logging.info(f"SpamBot response: {text[:120]}")
                                
                                # Arabic & English explicit restriction signs
                                negatives = ["unfortunately", "limited", "restrictions", "restricted",
                                             "can't message", "cannot message", "banned",
                                             "للاسف", "للأسف", "قيود", "مقيد", "محظور", "محدود"]
                                
                                if any(word in text for word in negatives):
                                    error_to_raise = "This account is spam-restricted."
                                else:
                                    logging.info("SpamBot check PASSED — account is clean.")
                                break # Processed
                        if spambot_replied:
                            break
                    
                    # If SpamBot never replied, treat as suspicious but don't block
                    if not spambot_replied:
                        logging.warning("SpamBot did not reply within timeout.")
                            
                except Exception as e:
                    err_type = type(e).__name__
                    err_msg = str(e).lower()
                    if "youblockeduser" in err_msg or "youblockeduser" in err_type.lower():
                        error_to_raise = "Please unblock @SpamBot on this account and try again. / يرجى إلغاء حظر بوت @SpamBot في هذا الحساب والمحاولة مرة أخرى."
                    elif any(x in err_type for x in ["PeerFlood", "UserRestricted", "Forbidden", "ChatWriteForbidden"]):
                        error_to_raise = f"This account is messaging-restricted/spam-blocked. ({err_type})"
                    elif any(x in err_type for x in ["Unauthorized", "UserDeactivated"]):
                        error_to_raise = f"Session revoked by Telegram. ({err_type})"
                    elif "peer_id_invalid" in err_msg:
                        error_to_raise = "This account cannot interact with bots — likely banned/restricted."
                    else:
                        logging.warning(f"Unexpected SpamBot check error: {e}")
                        error_to_raise = f"Could not verify account status via SpamBot. ({err_type})"

        except Exception as e:
            logging.error(f"Internal Health Check Error: {e}")
            if not error_to_raise:
                error_to_raise = f"Account session revoked or frozen. ({type(e).__name__})"

        if error_to_raise:
            try: await client.log_out()
            except: pass
            raise Exception(error_to_raise)

        session_string = await client.export_session_string()
        
        # 4. Generate & Enable 2FA
        import string
        two_fa_password = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        try:
            await client.enable_cloud_password(two_fa_password)
            logging.info(f"Enabled 2FA for {phone_number}: {two_fa_password}")
        except Exception as e:
            logging.warning(f"Failed to enable 2FA for {phone_number} (might already have one): {e}")
            two_fa_password = None # Mark as none if failed
            
        # 5. Check active sessions
        has_other_sessions = False
        try:
            from pyrogram.raw.functions.account import GetAuthorizations
            result = await client.invoke(GetAuthorizations())
            authorizations = result.authorizations
            # More than 1 means there's a session other than ours
            if len(authorizations) > 1:
                has_other_sessions = True
                logging.info(f"Account {phone_number} has {len(authorizations)-1} other active session(s). Requires 24h wait.")
        except Exception as e:
            logging.warning(f"Failed to fetch authorizations for {phone_number}: {e}")
            
        return {
            "session_string": session_string,
            "two_fa_password": two_fa_password,
            "has_other_sessions": has_other_sessions
        }
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
            match = re.search(r'\b(\d{5})\b', text)
            if match:
                code = match.group(1)
                break
    except (errors.AuthKeyInvalid, errors.AuthKeyUnregistered, errors.UserDeactivated, errors.SessionRevoked, errors.SessionExpired):
        raise Exception("SESSION_REVOKED")
    except Exception as e:
        logging.error(f"Error fetching code for session: {e}")
        raise e
    finally:
        if client.is_connected:
            await client.disconnect()
            
    return code

async def is_session_alive(session_string: str) -> tuple[bool, str]:
    try:
        client = await create_client(session_string)
        await client.connect()
        me = await client.get_me()
        if not me or me.is_scam or me.is_fake or me.is_restricted:
            logging.info(f"[AliveCheck] FAIL — API flags: scam={getattr(me,'is_scam',None)} fake={getattr(me,'is_fake',None)} restricted={getattr(me,'is_restricted',None)}")
            return False, "Account is frozen or banned."
        
        logging.info(f"[AliveCheck] API check passed for {getattr(me, 'phone_number', '?')}")

        # STRICT PHYSICAL CHECK: Try sending to Saved Messages (fails for frozen accounts)
        try:
            test_msg = await client.send_message("me", "✅")
            await test_msg.delete()
            logging.info("[AliveCheck] Saved Messages check PASSED.")
        except Exception as e:
            err_type = type(e).__name__
            logging.warning(f"[AliveCheck] Saved Messages check FAILED: {err_type} — {e}")
            return False, "Account is Frozen"

        # SPAM CHECK: Read SpamBot reply to detect spam-restricted accounts
        try:
            import time
            start_time = time.time()
            await client.send_message("SpamBot", "/start")
            
            spambot_replied = False
            for i in range(15):
                await asyncio.sleep(0.5)
                async for msg in client.get_chat_history("SpamBot", limit=3):
                    if msg.from_user and msg.from_user.id == 178220800 and msg.date.timestamp() > (start_time - 2):
                        text = (msg.text or "").lower()
                        spambot_replied = True
                        logging.info(f"[AliveCheck] SpamBot replied: {text[:100]}")
                        
                        negatives = ["unfortunately", "limited", "restrictions", "restricted",
                                     "can't message", "cannot message", "banned",
                                     "للاسف", "للأسف", "قيود", "مقيد", "محظور", "محدود"]
                        if any(word in text for word in negatives):
                            return False, "Account is Spam"
                        else:
                            return True, "" # SpamBot confirmed it is clean
                if spambot_replied:
                    break
                    
            if not spambot_replied:
                logging.warning("[AliveCheck] SpamBot did not reply during timeout. Assuming clean.")
                return True, "" # Assume ok if no error was thrown

        except Exception as e:
            err_type = type(e).__name__
            if any(x in err_type for x in ["PeerFlood", "UserRestricted", "Forbidden", "ChatWriteForbidden"]):
                return False, "Account is spam-restricted."
            # Any other error (PEER_ID_INVALID, Timeout, etc) = can't verify = reject
            return False, "Account is frozen or banned."
            
    except Exception as e:
        err_type = type(e).__name__
        err_str = str(e).lower()
        if "unauthorized" in err_str or "auth" in err_str or "session" in err_str:
            return False, "Bot session was removed."
        logging.warning(f"Session failed alive check: {e}")
        return False, "Account is frozen or banned."
    finally:
        try:
            if 'client' in locals() and client.is_connected:
                await client.disconnect()
        except:
            pass
