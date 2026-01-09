# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
#
# On shared hosting where compiling C extensions (like mysqlclient)
# fails because of missing client headers/build tools, prefer the
# pure-Python `PyMySQL` driver. If `PyMySQL` is installed it will
# register itself as `MySQLdb` so Django's MySQL backend works.
try:
	import pymysql
	pymysql.install_as_MySQLdb()
except Exception:
	# If PyMySQL isn't available, fall back to whatever is present
	# (e.g. mysqlclient). We avoid raising here to keep startup resilient.
	pass

from .celery import app as celery_app

__all__ = ('celery_app',)
