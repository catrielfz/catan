# Setup del entorno para usar esto

## Dependencias

Tener pip3 y python3 instalados.
`sudo apt-get install -y python3 python3-pip`

## Pasos

1. Instalar venv. En el root del proyecto.
Debe ser python3 o mas. Ej:
`virtualenv venv --python=python3.5`

2. Activar ese venv. El VSCode a veces lo hace solo cuando abris la terminal.
`source ./venv/bin/activate`

3. Una vez dentro del venv, instalar django con pip.
`pip install -r requirements.txt`

4. Ahora entramos a la app y creamos las migraciones.
`cd mesagames`
`python manage.py makemigrations catan`
`python manage.py migrate`

5. Ahora se puede ejecutar la webapp (siempre dentro del venv) con
el comando:
`python manage.py runserver`

Para salir del venv escribir en consola:
`deactivate`
