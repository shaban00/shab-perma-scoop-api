""" WSGI hook """

from scoop_rest_api import create_app

if __name__ == "__main__":
    create_app().run()
