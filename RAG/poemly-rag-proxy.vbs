Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Users\38107\Desktop\ai\RAG"
sh.Run "cmd /c """"C:\Users\38107\AppData\Local\Programs\Python\Python313\pythonw.exe"" ""C:\Users\38107\Desktop\ai\RAG\rag_proxy.py"" > ""C:\Users\38107\Desktop\ai\RAG\proxy_stdout.log"" 2>&1""", 0, False
