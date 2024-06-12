import os
import discord
from discord.ext import commands
import psycopg2
from psycopg2 import sql
from urllib.parse import urlparse
from datetime import datetime

# BASE DE DATOS
db_url = "postgres://xnhvxqot:GBxFhourd6vvxc0Mj3oewBqUuVvgwhp8@otto.db.elephantsql.com/xnhvxqot"
result = urlparse(db_url)
username = result.username
password = result.password
database = result.path[1:]
hostname = result.hostname
port = result.port

try:
  connection = psycopg2.connect(user=username,
                                password=password,
                                host=hostname,
                                port=port,
                                database=database)
  cursor = connection.cursor()
except (Exception, psycopg2.DatabaseError) as error:
  print(f"Error al conectar a la base de datos: {error}")

# CONEXIÓN CON BOT Y CONFIGURACIÓN

my_secret = os.environ.get('TOKEN')
if not my_secret:
  raise ValueError("No TOKEN found in environment variables")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# VISTAS Y FORMULARIOS, ACCIONES
class ConsultaView(discord.ui.View):

  @discord.ui.button(label="Realizar consulta",
                     style=discord.ButtonStyle.primary)
  async def open_form(self, interaction: discord.Interaction,
                      button: discord.ui.Button):
    await interaction.response.send_modal(ConsultaModal())


class FeedbackView(discord.ui.View):

  def __init__(self, consulta_id):
    super().__init__()
    self.consulta_id = consulta_id

  @discord.ui.button(label="Me ha servido la respuesta",
                     style=discord.ButtonStyle.success)
  async def button_yes(self, interaction: discord.Interaction,
                       button: discord.ui.Button):
    try:
      update_query = "UPDATE consultas SET estado = 'resuelta' WHERE id = %s"
      cursor.execute(update_query, (self.consulta_id, ))
      connection.commit()
      await interaction.response.send_message(
          "Gracias por tu feedback. Nos alegra que la respuesta te haya servido."
      )
    except (Exception, psycopg2.DatabaseError) as error:
      await interaction.response.send_message(
          f"Error al actualizar el estado: {error}. Vuelva a intentar más tarde o contacte a un administrador."
      )
      connection.rollback()

  @discord.ui.button(label="No me ha servido la respuesta",
                     style=discord.ButtonStyle.danger)
  async def button_no(self, interaction: discord.Interaction,
                      button: discord.ui.Button):
    await interaction.response.send_message(
        "Lamentamos que la respuesta no te haya servido, tu consulta será revisada por un administrador."
    )


class ConsultaModal(discord.ui.Modal, title="Consulta Formulario"):
  name = discord.ui.TextInput(label="Nombre", placeholder="Ingresa tu nombre")
  query = discord.ui.TextInput(label="Consulta",
                               style=discord.TextStyle.paragraph,
                               placeholder="Escribe tu consulta aquí")

  #FUNCIÓN CUANDO SE ENVÍAN LOS DATOS
  async def on_submit(self, interaction: discord.Interaction):
    name = self.name.value
    query = self.query.value
    fecha = datetime.now().date()
    hora = datetime.now().time()
    estado = "pendiente"
    nombre_usuario = interaction.user.name  # Nombre de usuario de Discord

    # RESPUESTA DE LA IA
    respuesta = "Esta es la respuesta de la IA..."

    # INSERTAR EN DATA BASE UNA VEZ FINALIZADO
    try:
      insert_query = """
            INSERT INTO consultas (nombre_usuario, nombre, fecha, hora, consulta, estado, respuesta)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """
      cursor.execute(
          insert_query,
          (nombre_usuario, name, fecha, hora, query, estado, respuesta))
      consulta_id = cursor.fetchone()[0]
      connection.commit()

      # RESPUESTA LUEGO DE GUARDAR EN LA BASE DE DATOS
      await interaction.response.send_message(f"{respuesta}",
                                              view=FeedbackView(consulta_id))
    except (Exception, psycopg2.DatabaseError) as error:
      await interaction.response.send_message(
          f"Error al registrar la consulta: {error}. Vuelva a intentar más tarde."
      )
      connection.rollback()


# COMANDOS DEL BOT
@bot.command(name="consulta")
async def consulta(ctx):
  await ctx.send(
      "Muy buenas! Si deseas realizar una consulta (alguna duda o pregunta sobre la materia), hace clic aquí:",
      view=ConsultaView())


# Correr bot
try:
  bot.run(my_secret)
except Exception as e:
  print(f"An error occurred: {e}")
