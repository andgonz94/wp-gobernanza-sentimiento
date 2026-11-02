SET FOREIGN_KEY_CHECKS=0;

DROP TABLE IF EXISTS detalle_error;
DROP TABLE IF EXISTS retroalimentacion;

CREATE TABLE retroalimentacion (
    id_registro            INT AUTO_INCREMENT PRIMARY KEY,
    texto                  TEXT NOT NULL,
    id_sesion              INT NULL,
    fecha_registro         DATE NULL,
    canal_captura          VARCHAR(50) NULL,
    ingesta_timestamp      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,retroalimentacion
    id_ejecucion           INT NULL,
    duracion_segundos      INT NULL,
    etiqueta_sentimiento   VARCHAR(20) NULL,
    confianza_etiqueta     VARCHAR(10) NULL,
    justificacion_etiqueta TEXT NULL,retroalimentacionid_sesion
    FOREIGN KEY (id_sesion)    REFERENCES sesion(id_sesion),
    FOREIGN KEY (id_ejecucion) REFERENCES ejecucion_pipeline(id_ejecucion)
);

CREATE TABLE detalle_error (
    id_error          INT AUTO_INCREMENT PRIMARY KEY,
    id_registro       INT NULL,
    id_ejecucion      INT NOT NULL,
    codigo_regla      VARCHAR(20) NOT NULL,
    descripcion       TEXT NOT NULL,
    valor_recibido    TEXT NULL,
    timestamp_error   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_ejecucion) REFERENCES ejecucion_pipeline(id_ejecucion)
);

SET FOREIGN_KEY_CHECKS=1;

select * from retroalimentacion;

CREATE TABLE segmento_retroalimentacion (
    id_segmento          INT AUTO_INCREMENT PRIMARY KEY,
    id_registro          INT NOT NULL,
    categoria            VARCHAR(50) NOT NULL,
    texto_segmento       TEXT NOT NULL,
    inicio_seg           FLOAT NULL,
    fin_seg              FLOAT NULL,
    etiqueta_sentimiento VARCHAR(20) NULL,
    confianza_etiqueta   VARCHAR(10) NULL,
    justificacion_etiqueta TEXT NULL,
    metodo_segmentacion  VARCHAR(20) DEFAULT 'automatico',
    FOREIGN KEY (id_registro) REFERENCES retroalimentacion(id_registro)
);


