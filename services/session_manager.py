import re
import logging
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
