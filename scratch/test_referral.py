import asyncio
from sqlalchemy import select
from database.engine import async_session
from database.models import User, AppSetting, Transaction, TransactionType

async def test_referral():
    user_id = 123456789
    referrer_id = 987654321
    
    async with async_session() as session:
        # 1. Setup - Create Referrer
        referrer = await session.get(User, referrer_id)
        if not referrer:
            referrer = User(id=referrer_id, balance_store=0.0, referral_earnings=0.0)
            session.add(referrer)
        else:
            referrer.balance_store = 0.0
            referrer.referral_earnings = 0.0
            
        # 2. Setup - Create User (Joined via Referrer)
        user = await session.get(User, user_id)
        if not user:
            user = User(id=user_id, referred_by=referrer_id, referral_bonus_awarded=False)
            session.add(user)
        else:
            user.referred_by = referrer_id
            user.referral_bonus_awarded = False
            
        # 3. Setup - Setting
        setting = await session.get(AppSetting, "referral_join_bonus")
        if not setting:
            session.add(AppSetting(key="referral_join_bonus", value="0.005"))
        else:
            setting.value = "0.005"
            
        await session.commit()
        print(f"Setup complete. Referrer balance: {referrer.balance_store}")

    # 4. Run Logic (Simulating cmd_start)
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user and user.referred_by and not user.referral_bonus_awarded:
            ref_id = user.referred_by
            # Use nested session like I did in my fix
            async with async_session() as ref_session:
                ref_obj = (await ref_session.execute(select(User).where(User.id == ref_id))).scalar_one_or_none()
                if ref_obj:
                    bonus_obj = (await ref_session.execute(select(AppSetting).where(AppSetting.key == "referral_join_bonus"))).scalar_one_or_none()
                    bonus_val = float(bonus_obj.value) if bonus_obj and bonus_obj.value else 0.005
                    
                    print(f"Awarding {bonus_val} to {ref_id}")
                    ref_obj.balance_store = (ref_obj.balance_store or 0.0) + bonus_val
                    ref_obj.referral_earnings = (ref_obj.referral_earnings or 0.0) + bonus_val
                    
                    user = await ref_session.merge(user)
                    user.referral_bonus_awarded = True
                    
                    txn = Transaction(user_id=ref_id, type=TransactionType.REFERRAL, amount=bonus_val)
                    ref_session.add(txn)
                    
                    await ref_session.commit()
                    print(f"Transaction committed.")

    # 5. Verify
    async with async_session() as session:
        ref_final = await session.get(User, referrer_id)
        user_final = await session.get(User, user_id)
        print(f"Final Referrer Balance: {ref_final.balance_store}")
        print(f"Final Referrer Earnings: {ref_final.referral_earnings}")
        print(f"Final User Awarded: {user_final.referral_bonus_awarded}")

if __name__ == "__main__":
    asyncio.run(test_referral())
