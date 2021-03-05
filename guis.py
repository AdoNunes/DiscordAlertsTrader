#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Feb 27 11:25:36 2021

@author: adonay
"""


import tkinter
from tkinter import simpledialog

import tkinter as tk
from tkinter import ttk
from tkinter.messagebox import showinfo


def popupmsg(msg):
    popup = tk.Tk()
    popup.wm_title("!")
    label = ttk.Label(popup, text=msg, font=("Verdana", 50))
    label.pack(side="top", fill="x", pady=10)
    B1 = ttk.Button(popup, text="Okay", command = popup.destroy)
    B1.pack()
    
    center(tk.Toplevel(popup))
    popup.mainloop()
    
    
def center(toplevel):
    toplevel.update_idletasks()
    
    screen_width = toplevel.winfo_screenwidth()
    screen_height = toplevel.winfo_screenheight()
   
    size = tuple(int(_) for _ in toplevel.geometry().split('+')[0].split('x'))
    x = screen_width/2 - size[0]/2
    y = screen_height/2 - size[1]/2

    toplevel.geometry("+%d+%d" % (x, y))
    toplevel.title("Centered!")    
 
    
def popup_bonus():
    win = tk.Toplevel()
    win.wm_title("Window")

    l = tk.Label(win, text="Input", width=200)
    l.grid(row=0, column=0)

    b = ttk.Button(win, text="Okay", width=200, command=win.destroy)
    b.grid(row=1, column=0)

def popup_showinfo():
    showinfo("Window", "Hello World!")

class Application(ttk.Frame):

    def __init__(self, master):
        ttk.Frame.__init__(self, master)
        self.pack()

        self.button_bonus = ttk.Button(self, text="Bonuses", width=200, command=popup_bonus)
        self.button_bonus.pack()

        self.button_showinfo = ttk.Button(self, text="Show Info", width=200, command=popup_showinfo)
        self.button_showinfo.pack()

root = tk.Tk()

app = Application(root)

root.mainloop()
        
        
parent = tkinter.Tk() # Create the object
parent["height"] = 400;
parent["width"] = 500;

parent.overrideredirect(1) # Avoid it appearing and then disappearing quickly
# parent.iconbitmap("PythonIcon.ico") # Set an icon (this is optional - must be in a .ico format)
parent.withdraw() # Hide the window as we do not want to see this one

string_value = simpledialog.askstring('Dialog Title', 'What is your name?', parent=parent)








root = tk.Tk() 
  
# Adding widgets to the root window 
ttk.Label(root, text = 'GeeksforGeeks',  
      font =('Verdana', 15)).pack(side = ttk.TOP, pady = 10) 
  
Button(root, text = 'Click Me !').pack(side = TOP) 
  
mainloop() 



