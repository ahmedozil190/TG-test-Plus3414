try:
    from web_admin import app
    print("Web Admin imported successfully")
except Exception as e:
    import traceback
    traceback.print_exc()
