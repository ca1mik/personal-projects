def in_virtual_screen(bounds,x,y):
    left,top,width,height=bounds
    return left<=x<left+width and top<=y<top+height

def literal_keys(text):
    escapes={'{':'{{}','}':'{}}','+':'{+}','^':'{^}','%':'{%}','~':'{~}','(':'{(}',')':'{)}'}
    return ''.join(escapes.get(c,c) for c in text)

def require_target(expected,foreground):
    if expected is None:raise ValueError('Перед вводом выберите окно действием focus; затем проверьте снимок.')
    if foreground!=expected:raise ValueError('Фокус окна изменился. Ввод остановлен, чтобы не попасть в другое приложение.')
