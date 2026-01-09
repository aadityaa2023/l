# Django Deployment Instructions for Domainz Shared Hosting

## Fixed Issues
The directory listing issue has been resolved by fixing the following:

1. **Updated `.htaccess`** - Removed placeholder paths and configured Apache/Passenger correctly
2. **Updated `passenger_wsgi.py`** - Added production environment loading and improved virtualenv activation
3. **Updated `.env`** - Set production configuration (DEBUG=False, HTTPS settings, MySQL database)

## Steps to Complete Deployment on Server

### 1. Upload Files to Server
Upload all files to your Domainz hosting account at:
- `public_html/` or `leqaudio.com/` directory (wherever your domain points)

Make sure these files are uploaded:
- `.htaccess`
- `passenger_wsgi.py`
- `.env` (or `.env.production`)
- All Django project files

### 2. Set Up Python Virtual Environment
Via Domainz/cPanel Python selector:
1. Go to cPanel → Python Selector or Setup Python App
2. Create a Python 3.10+ application
3. Set the application root to your leq project directory
4. Install requirements: `pip install -r requirements.txt`

### 3. Configure Database
The `.env` file is configured for MySQL:
```
DB_NAME=leqaudio_l
DB_USER=leqaudio_l
DB_PASSWORD='Aditya@2327'
```

Make sure:
1. MySQL database `leqaudio_l` exists in cPanel
2. Database user `leqaudio_l` has full permissions
3. Password is correct

### 4. Run Database Migrations
SSH into your server or use cPanel terminal:
```bash
cd ~/public_html/leq  # or your project directory
source ~/virtualenv/leqaudio_com/3.10/bin/activate  # activate virtualenv
python manage.py migrate
```

### 5. Collect Static Files
```bash
python manage.py collectstatic --noinput
```

This will collect all static files to the `staticfiles/` directory.

### 6. Create Superuser (Optional)
```bash
python manage.py createsuperuser
```

### 7. Restart Application
In cPanel:
1. Go to Python Selector or Setup Python App
2. Click "Restart" button

Or create a `tmp/restart.txt` file:
```bash
mkdir -p tmp
touch tmp/restart.txt
```

### 8. Test the Application
Visit: https://leqaudio.com

You should see your Django application instead of directory listing.

## Troubleshooting

### Still seeing directory listing?
1. Check that `.htaccess` exists in the root directory
2. Verify Apache mod_rewrite is enabled (should be enabled by default)
3. Check file permissions: `.htaccess` should be 644
4. Touch restart file: `touch tmp/restart.txt`

### Application errors?
1. Check error logs in cPanel → Errors
2. Add `print()` statements in `passenger_wsgi.py` to debug
3. Verify virtualenv path in passenger_wsgi.py matches your actual virtualenv location

### Database connection errors?
1. Verify MySQL credentials in `.env`
2. Check if `mysql-connector-python` or `mysqlclient` is installed
3. Run migrations: `python manage.py migrate`

### Static files not loading?
1. Run `python manage.py collectstatic`
2. Verify STATIC_ROOT in settings.py
3. Check that static files are in `staticfiles/` directory

### Permission errors?
Set correct permissions:
```bash
chmod 644 .htaccess
chmod 644 passenger_wsgi.py
chmod 600 .env
chmod 755 manage.py
```

## Important Security Notes

1. **Never commit `.env` to Git** - It contains sensitive credentials
2. **Verify DEBUG=False** in production
3. **Use HTTPS** - SSL certificate should be active (Let's Encrypt via cPanel)
4. **Keep SECRET_KEY secret** - Don't share it

## File Locations Reference

Common virtualenv paths on Domainz/cPanel:
- `~/virtualenv/leqaudio_com/3.10/`
- `~/virtualenv/leqaudio.com/3.10/`
- `~/.virtualenvs/leq/`

The `passenger_wsgi.py` will try all common paths automatically.

## Next Steps After Deployment

1. Monitor application logs for errors
2. Set up SSL certificate (should be auto via Let's Encrypt)
3. Test all functionality:
   - User registration/login
   - Course viewing
   - Payment processing
   - Email sending
4. Set up backup strategy for database and media files
5. Consider using production Razorpay keys instead of test keys

## Contact Support
If issues persist, contact Domainz support with:
- Error logs from cPanel
- Output from `passenger_wsgi.py` (check logs)
- Python version and installed packages list
