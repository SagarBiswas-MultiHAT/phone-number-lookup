import traceback
try:
    import phoneint.gui as g
    print('imported phoneint.gui OK')
except Exception:
    traceback.print_exc()
