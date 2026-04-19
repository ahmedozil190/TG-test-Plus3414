import re
import logging
import asyncio
from pyrogram import Client, errors
from pyrogram.raw import functions, types
from typing import Dict

from config import API_ID, API_HASH

# We store temporary clients here during the sign-in flow
login_clients: Dict[int, Client] = {}

async def create_client(session_string: str = None) -> Client:
    if session_string:
        client = Client(name="temp", api_id=API_ID, api_hash=API_HASH, session_string=session_string, in_memory=True)
    else:
        client = Client(name="temp", api_id=API_ID, api_hash=API_HASH, in_memory=True)
    return client

async def request_app_code(user_id: int, phone_number: str) -> str:
    """Returns phone_code_hash"""
    client = await create_client()
    await client.connect()
    
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
        return None
        
    try:
        await client.sign_in(phone_number, phone_code_hash, phone_code)
        
        # Health Check: Deep inspection after login
        try:
            me = await client.get_me()
            # 1. Check for Scam/Fake/Restricted flags in User Object
            if me.is_scam or me.is_fake or me.is_restricted:
                await client.log_out()
                if me.is_restricted:
                    raise Exception("This account is restricted or spam-blocked.")
                raise Exception("This account is frozen by Telegram.")
            
            # 2. Check for Spam Info from MTProto API
            spam_info = await client.invoke(functions.account.GetSpamInfo())
            if not isinstance(spam_info, types.messages.SpamFilterNone):
                await client.log_out()
                raise Exception("This account is restricted or spam-blocked.")

            # 3. HUMAN-GRADE CHECK: Interact with @SpamBot (ID: 178220800)
            try:
                import time
                start_time = time.time()
                target_bot = 178220800
                print(f"DEBUG: STARTING HARD CHECK for {phone_number} at {start_time}")
                
                # Ensure the bot is unblocked first
                try:
                    await client.unblock_user(target_bot)
                except: pass
                
                # Send /start to @SpamBot
                await client.send_message(target_bot, "/start")
                print(f"DEBUG: Message sent to @SpamBot for {phone_number}")
                
                # Wait up to 7 seconds for a FRESH response
                response_received = False
                for i in range(14): # 14 * 0.5s = 7s
                    await asyncio.sleep(0.5)
                    async for message in client.get_chat_history(target_bot, limit=3):
                        # MUST be FROM the bot AND NOT our message AND NEWER than start_time
                        msg_timestamp = message.date.timestamp()
                        if message.from_user and message.from_user.id == target_bot and msg_timestamp >= (start_time - 1):
                            msg_text = (message.text or "").lower()
                            print(f"DEBUG: SpamBot [{phone_number}] Response: {msg_text[:100]}...")
                            
                            # Standard success phrases for CLEAN accounts
                            if "good news" in msg_text or "no limits" in msg_text or "birds" in msg_text:
                                response_received = True
                                print(f"DEBUG: Account {phone_number} is POSITIVELY CLEAN")
                                break
                            else:
                                print(f"DEBUG: Account {phone_number} is POSITIVELY RESTRICTED")
                                await client.log_out()
                                raise Exception("This account is restricted or spam-blocked.")
                    if response_received: break
                
                if not response_received:
                    print(f"DEBUG: CRITICAL - SpamBot DID NOT RESPOND for {phone_number} after 7 seconds.")
                    await client.log_out()
                    raise Exception("Security check failed: SpamBot not responding. Please try again.")
                    
            except Exception as e:
                # If we manually raised an exception, pass it up
                if any(msg in str(e) for msg in ["restricted", "spam-blocked", "frozen", "Security check", "not responding"]):
                    raise e
                # Fallback for any other errors (log them and fail safe by rejecting)
                print(f"DEBUG: SpamBot CHECK EXCEPTION: {type(e).__name__}: {e}")
                await client.log_out()
                raise Exception("This account is restricted or spam-blocked.")
                
        except Exception as e:
            # If we manually raised an exception, pass it up
            if any(msg in str(e) for msg in ["restricted", "spam-blocked", "frozen"]):
                raise e
            # Ignore other errors during health check to avoid false negatives
            pass

        session_string = await client.export_session_string()
        return session_string
    except Exception as e:
        # If it was a login-level frozen error
        if "UserDeactivated" in str(e):
             raise Exception("This account is frozen by Telegram.")
        raise e
    finally:
        if client.is_connected:
            await client.disconnect()
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
