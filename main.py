from dotenv import load_dotenv
load_dotenv()

from gui import FileAssistantApp

if __name__ == "__main__":
    app = FileAssistantApp()
    app.mainloop()
