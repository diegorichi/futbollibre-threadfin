import os

from dotenv import dotenv_values

from server.services.agenda_service import AgendaService


def procesar_y_notificar():
    service = AgendaService(dotenv_values(os.getenv("ENV_FILE", ".env")))
    print("iniciando actualización de agenda")
    print(service.update_ntfy())


if __name__ == "__main__":
    procesar_y_notificar()
