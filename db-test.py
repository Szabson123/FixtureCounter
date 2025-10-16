import pyodbc
import pandas as pd
import os

hostname = "psu62pdb2.production.bitron.group"
database = "master"
password = "koh1234"
user = "sa"

# conn = pyodbc.connect(
#                 f"DRIVER={{SQL Server}};"
#                 f"SERVER={hostname};"
#                 f"DATABASE={database};"
#                 f"UID={user};"
#                 f"PWD={password};"
#             )
# try:
#     print("Połączono z bazą:", database)

#     query = """SELECT name FROM sys.databases WHERE LEFT(name, 3) = 'SPI';"""
#     df = pd.read_sql(query, conn)

#     if not df.empty:
#         baza_lista = df["name"].to_list()
#         print("Znalezione bazy:", baza_lista)
#     else:
#         print("Nie znaleziono baz zaczynających się na 'SPI'.")

# except Exception as e:
#     print("Błąd:", e)

# finally:
#     conn.close()
#     print("Połączenie zamknięte.")

# wybrana_baza = 'SPI_SS_SL_02935'

# conn = pyodbc.connect(
#     f"DRIVER={{SQL Server}};"
#     f"SERVER={hostname};"
#     f"DATABASE={wybrana_baza};"
#     f"UID={user};"
#     f"PWD={password};"
# )

# print(f"Połączono z bazą: {wybrana_baza}")

# df = pd.read_sql("SELECT * FROM [dbo].[Pcb202510];", conn)
# print(df)

# conn.close()

# --- KATALOG WYJŚCIOWY ---
output_dir = "wyniki"
os.makedirs(output_dir, exist_ok=True)

conn = pyodbc.connect(
    f"DRIVER={{SQL Server}};"
    f"SERVER={hostname};"
    f"DATABASE={database};"
    f"UID={user};"
    f"PWD={password};"
)

try:
    print("Połączono z master")

    query = """SELECT name FROM sys.databases WHERE LEFT(name, 3) = 'SPI';"""
    df_bazy = pd.read_sql(query, conn)

    if df_bazy.empty:
        print("Nie znaleziono żadnych baz zaczynających się na 'SPI'.")
    else:
        baza_lista = df_bazy["name"].to_list()
        print("Znalezione bazy:", baza_lista)

finally:
    conn.close()
    print("Połączenie z master zamknięte.\n")

for baza in baza_lista:
    print(f"Łączenie z bazą: {baza}")

    try:
        conn = pyodbc.connect(
            f"DRIVER={{SQL Server}};"
            f"SERVER={hostname};"
            f"DATABASE={baza};"
            f"UID={user};"
            f"PWD={password};"
        )

        query = "SELECT * FROM [dbo].[Pcb202510];"
        df = pd.read_sql(query, conn)

        if not df.empty:
            file_path = os.path.join(output_dir, f"{baza}.csv")
            df.to_csv(file_path, index=False, encoding="utf-8-sig")
            print(f"Zapisano dane z bazy {baza} do pliku: {file_path}")
        else:
            print(f"Brak danych w tabeli Pcb202510 dla bazy {baza}.")

    except Exception as e:
        print(f"Błąd przy bazie {baza}: {e}")

    finally:
        conn.close()

print("\nGotowe! Wszystkie dostępne dane zostały zapisane do folderu 'wyniki'.")