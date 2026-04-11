# Reverse engineering notes of Ingenium devices

# Architecture

tbc.

# Global system configuration

```
Globals.tipoConexion == 0 // Ingenium (Cloud) Webserver
```

# Network connections

| Port        | Description             |
| ----------- | ----------------------- |
| `tcp/8000`  | Web server / -interface |
| `tcp/12347` | ETHBUSIII daemon        |

# Web server content

Initialization of the client is initially web based (port 8000 webserver)

| URI           | Description                                             |
| ------------- | ------------------------------------------------------- |
| `/CONFIG.TXT` | Touch display device configuration                      |
| `/Instal.dat` | List of connecting BUSing devices with their properties |
| `/dir_busing` | tbd.                                                    |
| `/v3_0`       | Indicates (later?) V3.0 devices or KNX type device      |

# Android Application

Android app : `com.ingenium.ingeniumasc`

## 1. Ingenium MainThread cargar activity

Determine connection type (cloud vs. local network) and connection state

```
if (Globals.tipoConexion == 0) {
    Globals.ipEthBus = Globals.ipServidor;
    Globals.userEthBus = Globals.arrayConexiones.get(Globals.conexionSeleccionada).user;
    Globals.passEthBus = Globals.arrayConexiones.get(Globals.conexionSeleccionada).password;
} else {
    Globals.ipEthBus = Globals.arrayConexiones.get(Globals.conexionSeleccionada).ip;
    if (!ethbusAccesible()) {
        // Shows connection issue warning dialog
        return // makes early return
    }
}

// Continue async with Step 2, initialization
new cargaAsincronaTask().execute(new Void[0]);
```

## 2. Asynchronous initialization of "Project"

Irrespective of the connection type, the initialization makes local copies of the Ingenium device configuration (filesystem) and initializes the Planos (screens) and Devices (dispositivos):

```
if (Globals.tipoConexion == 1) {
    MainActivity.this.cargaLocal();
} else {
    this.result = MainActivity.this.cargaRemota();
}
ConfiguracionProyecto config = new ConfiguracionProyecto(MainActivity.this);
config.configurarArrayPlanos();
config.configurarArrayDispositivos();
Globals.check_infobar_out_mode();
return null;
```

## 3. Reading current state
Ingenium App opens with messages that trigger a (full?) devices status dump:

```
Received: {'raw': 'fefe0afffffefe0000', 'command': 10, 'origin': 65535, 'destination': 65278, 'data1': 0, 'data2': 0}
Received: {'raw': 'fefe01fefe00ff0000', 'command': 1, 'origin': 65278, 'destination': 255, 'data1': 0, 'data2': 0}
```

Messages are decoded in 9-bytes sequences:
```
p_result2.comando = recBuffer[2];
p_result2.destino = (short) (
    (recBuffer[3] << 8) + (recBuffer[4] & 255));
p_result2.origen = (short) (
    (recBuffer[5] << 8) + (recBuffer[6] & 255));
p_result2.dato1 = recBuffer[7] & 255;
p_result2.dato2 = recBuffer[8] & 255;
```
## SQLite database

Basic local (Android) SQLite database

### Initialization

Creates database structure and loads stored connections (web or local)

```
    Globals.sqliteManager = new SQLiteManager(this);
    Globals.sqliteManager.init_database();
    Globals.sqliteManager.obtenerDatos();

    public void init_database() {
            db.execSQL("CREATE TABLE datos_generales (clave text primary key, valor text)");
            db.execSQL("INSERT INTO datos_generales (clave, valor) VALUES ('tipo_conexion', 'remota')");
            db.execSQL("CREATE TABLE conexion (nombre text primary key, user text, password text, id_ethbus text, ip text, password_intrusion text, foto text, conexion text)");
            db.execSQL("CREATE TABLE datos_conexion (nombre TEXT REFERENCES conexion (nombre) ON DELETE CASCADE, field TEXT, value TEXT, PRIMARY KEY (nombre, field))");
            db.execSQL("CREATE TABLE camara (nombre text, conexion text)");

    public void obtenerDatos() {
        Globals.arrayConexiones.clear();
        SQLiteDatabase db = getWritableDatabase();
        Cursor cursor = db.rawQuery("SELECT * FROM conexion", null);

```

### Connections table

```
        con.nombre = getPreferenceScreen().getSharedPreferences().getString(KEY_NOMBRE, "");
        con.user = getPreferenceScreen().getSharedPreferences().getString(KEY_USER, "");
        con.password = getPreferenceScreen().getSharedPreferences().getString(KEY_PASS, "");
        con.id_ethbus = this.id_eth;
        con.ip = getPreferenceScreen().getSharedPreferences().getString(KEY_IP_LOCAL, "");
        con.password_intrusion = getPreferenceScreen().getSharedPreferences().getString(KEY_PASS, "");
        con.foto = "screen.jpg";
        con.conexion = getPreferenceScreen().getSharedPreferences().getBoolean(KEY_LOCAL_ACTIVATION, false) ? "local" : "remota";
```

# ETHBUSIII (BUSing) communication

## General binary format

Cloud differs from local webserver:

```
                Log.i("Comunicacion enviado", "comando: " + p.comando + " or: " + Globals.DirToKNX(Integer.valueOf(p.origen)) + " dr: " + Globals.DirToKNX(Integer.valueOf(p.destino)) + " d1: " + p.dato1 + " d2: " + p.dato2);
                byte[] strBuffer = new byte[7];
                if (Globals.tipoConexion == 0) {
                    strBuffer[0] = (byte) (p.destino >> 8);
                    strBuffer[1] = (byte) p.destino;
                    strBuffer[2] = -2;
                    strBuffer[3] = -2;
                    strBuffer[4] = (byte) p.comando;
                    strBuffer[5] = (byte) p.dato1;
                    strBuffer[6] = (byte) p.dato2;
                    this.cabecera[0] = -1;
                    this.cabecera[1] = -1;
                    this.out.write(this.cabecera);
                } else {
                    strBuffer[0] = -1;
                    strBuffer[1] = -1;
                    strBuffer[2] = (byte) (p.destino >> 8);
                    strBuffer[3] = (byte) p.destino;
                    strBuffer[4] = (byte) p.comando;
                    strBuffer[5] = (byte) p.dato1;
                    strBuffer[6] = (byte) p.dato2;
                }

```
