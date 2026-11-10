"""Comprueba la versión mínima de Python. Código de salida 0 si es válida."""
import sys

if sys.version_info < (3, 11):
    print(f"Python {sys.version.split()[0]} es demasiado antiguo: se necesita 3.11 o superior.")
    raise SystemExit(1)
print(f"Python {sys.version.split()[0]}")
