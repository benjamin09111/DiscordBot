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

  # FUNCIÓN CUANDO SE ENVÍAN LOS DATOS
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


@bot.command(name="actualiza")
async def actualiza(ctx, consulta_id: int, estado: str):
  """
    Actualiza el estado de una consulta específica por su ID.

    Uso: !actualiza <consulta_id> <estado>
    Ejemplo: !actualiza 1 resuelta
    """
  valid_estados = ["pendiente", "resuelta"]
  if estado not in valid_estados:
    await ctx.send(
        f"Estado inválido. Los estados válidos son: {', '.join(valid_estados)}"
    )
    return

  try:
    update_query = "UPDATE consultas SET estado = %s WHERE id = %s"
    cursor.execute(update_query, (estado, consulta_id))
    if cursor.rowcount == 0:
      await ctx.send(
          f"No se encontró ninguna consulta con el ID {consulta_id}.")
    else:
      connection.commit()
      await ctx.send(
          f"La consulta con ID {consulta_id} ha sido actualizada a {estado}.")
  except (Exception, psycopg2.DatabaseError) as error:
    await ctx.send(f"Error al actualizar la consulta: {error}.")
    connection.rollback()


@bot.command(name="limpiar")
async def limpiar(ctx):
  """
    Elimina todas las consultas que ya están resueltas de la base de datos.

    Uso: !limpiar
    """
  try:
    delete_query = "DELETE FROM consultas WHERE estado = 'resuelta'"
    cursor.execute(delete_query)
    connection.commit()
    await ctx.send("Todas las consultas resueltas han sido eliminadas.")
  except (Exception, psycopg2.DatabaseError) as error:
    await ctx.send(f"Error al limpiar las consultas: {error}.")
    connection.rollback()


@bot.command(name="excel")
async def excel(ctx):
  """
    Genera un archivo Excel con todos los registros almacenados en la base de datos.

    Uso: !excel
    """
  try:
    select_query = "SELECT * FROM consultas"
    cursor.execute(select_query)
    registros = cursor.fetchall()

    # Generar el archivo Excel
    import pandas as pd
    df = pd.DataFrame(registros,
                      columns=[desc[0] for desc in cursor.description])
    # Guardar el archivo Excel
    file_path = "/tmp/consultas.xlsx"
    df.to_excel(file_path, index=False)

    # Enviar el archivo Excel
    await ctx.send(file=discord.File(file_path))
  except (Exception, psycopg2.DatabaseError) as error:
    await ctx.send(f"Error al generar el archivo Excel: {error}.")


@bot.command(name="pendientes")
async def pendientes(ctx):
  """
    Genera un archivo Excel con todas las consultas pendientes en la base de datos.

    Uso: !pendientes
    """
  try:
    select_query = "SELECT * FROM consultas WHERE estado = 'pendiente'"
    cursor.execute(select_query)
    registros = cursor.fetchall()

    # Generar el archivo Excel
    import pandas as pd
    df = pd.DataFrame(registros,
                      columns=[desc[0] for desc in cursor.description])
    # Guardar el archivo Excel
    file_path = "/tmp/consultas_pendientes.xlsx"
    df.to_excel(file_path, index=False)

    # Enviar el archivo Excel
    await ctx.send(file=discord.File(file_path))
  except (Exception, psycopg2.DatabaseError) as error:
    await ctx.send(f"Error al generar el archivo Excel: {error}.")


@bot.command(name="actualizar")
async def actualizar(ctx, *consulta_ids: int):
  """
    Cambia el estado de varias consultas a 'resuelta' usando sus IDs.

    Uso: !actualizar <ID1> <ID2> ...
    Ejemplo: !actualizar 1 2 3
    """
  try:
    for consulta_id in consulta_ids:
      update_query = "UPDATE consultas SET estado = 'resuelta' WHERE id = %s"
      cursor.execute(update_query, (consulta_id, ))
      connection.commit()
    await ctx.send(
        f"Las consultas con IDs {', '.join(map(str, consulta_ids))} han sido actualizadas a 'resuelta'."
    )
  except (Exception, psycopg2.DatabaseError) as error:
    await ctx.send(f"Error al actualizar las consultas: {error}.")
    connection.rollback()


@bot.command(name="ayuda")
async def ayuda(ctx):
  """
    Muestra una lista de todos los comandos disponibles y cómo usarlos.

    Uso: !ayuda
    """
  ayuda_texto = """
    **Lista de comandos disponibles:**

    1. `!consulta`: Abre un formulario para realizar una consulta.

    2. `!actualiza <consulta_id> <estado>`: Actualiza el estado de una consulta específica por su ID.
       Ejemplo: `!actualiza 1 resuelta`

    3. `!limpiar`: Elimina todas las consultas que ya están resueltas de la base de datos.
       Ejemplo: `!limpiar`

    4. `!excel`: Genera un archivo Excel con todos los registros almacenados en la base de datos.
       Ejemplo: `!excel`

    5. `!pendientes`: Genera un archivo Excel con todas las consultas pendientes en la base de datos.
       Ejemplo: `!pendientes`

    6. `!actualizar <ID1>, <ID2>, ...`: Cambia el estado de varias consultas a 'resuelta' usando sus IDs.
       Ejemplo: `!actualizar 1, 2, 3`

    7. `!ver`: Muestra todos los registros de la base de datos.
       Ejemplo: `!ver`
    """
  await ctx.send(ayuda_texto)


@bot.command(name="ver")
async def ver(ctx):
  """
    Muestra todos los registros de la base de datos sin paginación.

    Uso: !ver
    """
  try:
    select_query = "SELECT * FROM consultas"
    cursor.execute(select_query)
    registros = cursor.fetchall()

    if not registros:
      await ctx.send("No hay registros en la base de datos.")
      return

    embed = discord.Embed(title="Registros en la base de datos")
    for registro in registros:
      embed.add_field(
          name=f"ID: {registro[0]}",
          value=
          f"Usuario: {registro[1]}\nNombre: {registro[2]}\nFecha: {registro[3]}\nHora: {registro[4]}\nConsulta: {registro[5]}\nEstado: {registro[6]}\nRespuesta: {registro[7]}",
          inline=False)

    await ctx.send(embed=embed)

  except (Exception, psycopg2.DatabaseError) as error:
    await ctx.send(f"Error al obtener los registros: {error}.")


# INICIAR BOT
bot.run(my_secret)
