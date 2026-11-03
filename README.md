# Control de combustible

Aplicació Streamlit per registrar repostatges dels teus cotxes i consultar despesa, litres i consum anual.

## Posada en marxa

```powershell
pip install -r requirements.txt
streamlit run app.py
```

Abans d'iniciar-la, crea `.streamlit/secrets.toml` a partir de [`.streamlit/secrets.toml.example`](./.streamlit/secrets.toml.example) i defineix una contrasenya llarga i única. L'aplicació no s'obre sense aquesta contrasenya.

Per usar-la des del mòbil connectat a la mateixa Wi-Fi, inicia-la amb:

```powershell
streamlit run app.py --server.address 0.0.0.0
```

Obre al mòbil l'adreça `http://IP_DEL_TEU_ORDINADOR:8501`.

Les dades es desen localment a `data/repostatges.csv` i `data/cotxes.json`. Fes una còpia d'aquesta carpeta per tenir una còpia de seguretat.

## Publicació a Streamlit Community Cloud

Per publicar-la com una aplicació separada i sense afectar la calculadora energètica, crea un repositori GitHub nou només per a aquesta aplicació i puja-hi el contingut d'aquesta carpeta. A Streamlit Community Cloud, crea una aplicació seleccionant aquest repositori, la branca principal i `app.py` com a fitxer principal. La calculadora pot continuar desplegada en una altra aplicació del mateix compte.

Streamlit Community Cloud no garanteix la persistència dels fitxers locals. Per conservar les dades entre sessions i dispositius:

1. Crea un projecte a Supabase i executa el contingut de [`supabase_schema.sql`](./supabase_schema.sql) a l'SQL Editor.
2. A la configuració de secrets de l'aplicació de Streamlit, copia l'estructura de [`.streamlit/secrets.toml.example`](./.streamlit/secrets.toml.example). Tria una contrasenya d'accés llarga i única i substitueix els valors de Supabase pels del teu projecte.
3. Fes servir la clau `service_role` només com a secret del servidor; no la publiquis ni la comparteixis. L'aplicació demanarà la contrasenya abans de mostrar o modificar dades. Si Streamlit permet limitar l'accés de l'app, fes-ho també i no comparteixis la contrasenya.

Quan Supabase està configurat, els cotxes i repostatges es desen a la base de dades. Sense aquesta configuració, l'aplicació continua funcionant amb fitxers locals, però les dades del desplegament al núvol poden perdre's.

### Accés des del mòbil

Obre l'enllaç de l'aplicació desplegada al navegador del mòbil i inicia sessió a Streamlit si l'aplicació és privada. A Android, obre el menú del navegador i tria **Afegeix a la pantalla d'inici** o **Instal·la l'aplicació**. A iPhone, obre l'enllaç amb Safari, toca **Compartir** i tria **Afegeix a la pantalla d'inici**. Això crea una icona d'accés directe; l'aplicació continua funcionant en línia.

## Eliminació segura de repostatges

A la pestanya **Historial**, obre **Elimina un repostatge** i selecciona el registre. L'aplicació mostra la data, el cotxe, els litres, el cost i el quilometratge abans de demanar una segona confirmació. Després d'eliminar-lo, verifica que el registre ja no es troba al fitxer local o a Supabase i torna a carregar l'historial. L'operació és definitiva.

## Com es calcula el consum

Introdueix la lectura total del comptaquilòmetres a cada repostatge. L'aplicació recorda l'última lectura de cada cotxe, mostra la diferència i la calcula automàticament a l'historial. El consum en L/100 km només apareix entre dos repostatges marcats com a “He omplert el dipòsit”: litres del segon repostatge ÷ quilòmetres recorreguts × 100.
