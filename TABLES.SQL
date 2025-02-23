CREATE TABLE public.url_jesus (
    id integer NOT NULL DEFAULT nextval('url_jesus_id_seq'::regclass),
    url text,
    city text
);

CREATE TABLE public.empresas_noprimary (
    id integer NOT NULL DEFAULT nextval('empresas_noprimary_id_seq'::regclass),
    nombre character varying(255),
    resumen text,
    telefono character varying(50),
    tamano character varying(50),
    ubicaciones text,
    fundacion character varying(50),
    sector text[],
    sitio_web text[],
    sede text[],
    especialidades text[],
    codigo_postal character varying(10),
    ciudad character varying(255)
);
