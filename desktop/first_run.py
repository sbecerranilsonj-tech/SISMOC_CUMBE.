"""Configurar la cuenta de Contabilidad en una instalación nueva, sin clave predefinida."""

def crear_cuenta_inicial():
    from django.contrib.auth import get_user_model
    User=get_user_model()
    if User.objects.filter(is_active=True,rol__in=['CONTADORA','ADMINISTRADOR','GERENTE_GENERAL']).exists():
        return True
    import tkinter as tk
    from tkinter import ttk,messagebox
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError
    root=tk.Tk();root.title('Bienvenida a SISMOC El Cumbe');root.geometry('460x410');root.resizable(False,False)
    frame=ttk.Frame(root,padding=28);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Configura tu cuenta',font=('Segoe UI',18,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Esta cuenta administrará la información de la empresa.',wraplength=390).pack(anchor='w',pady=(6,18))
    fields=[]
    for label,secret in [('Usuario',False),('Contraseña (mínimo 12 caracteres)',True),('Repetir contraseña',True)]:
        ttk.Label(frame,text=label).pack(anchor='w',pady=(6,4))
        field=ttk.Entry(frame,show='*' if secret else '');field.pack(fill='x');fields.append(field)
    done=[]
    def save():
        username=fields[0].get().strip();password=fields[1].get()
        try:
            if not username:raise ValueError('Indica un nombre de usuario.')
            if len(password)<12 or password!=fields[2].get():raise ValueError('Usa al menos 12 caracteres y repite la misma contraseña.')
            u=User(username=username,email='');u.full_clean(exclude=['password'])
            validate_password(password,u)
            User.objects.create_user(username=username,email='',password=password,rol='CONTADORA',dni=None,is_staff=True)
        except (ValueError,ValidationError) as e:
            messagebox.showerror('Revisa los datos','\n'.join(e.messages) if isinstance(e,ValidationError) else str(e));return
        done.append(True);root.destroy()
    ttk.Button(frame,text='Crear cuenta y comenzar',command=save).pack(fill='x',pady=(24,0))
    fields[0].focus();root.mainloop()
    return bool(done)
