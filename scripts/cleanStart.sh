#!/bin/bash


rm db.sqlite3
rm core/migrations/0004_doctoravailability.py
rm core/migrations/0005_alter_doctoravailability_options_and_more.py
rm -fr core/migrations/__pycache__/



python3 manage.py makemigrations
python3 manage.py migrate
python3 manage.py createsuperuser
