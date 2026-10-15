-- Busqueda avanzada por texto con FTS5 sobre Biblioteca.
-- La tabla virtual NO duplica el contenido (content= apunta a Biblioteca) y
-- los triggers la mantienen sincronizada en INSERT/UPDATE/DELETE.
-- unicode61 con remove_diacritics=2: insensible a mayusculas y a tildes
-- (rustico encuentra "Rústico"), adecuado para texto en español.

CREATE VIRTUAL TABLE `biblioteca_fts` USING fts5(
	`Titulo`,
	`Autor`,
	`Coautor`,
	`Tema o Materia`,
	`Series`,
	`Notas`,
	`Texto Ficha`,
	`Cota`,
	`ISBN`,
	content='Biblioteca',
	content_rowid='ID',
	tokenize='unicode61 remove_diacritics 2'
);
--> statement-breakpoint
CREATE TRIGGER `trg_biblioteca_fts_ai` AFTER INSERT ON `Biblioteca` BEGIN
	INSERT INTO `biblioteca_fts`(rowid, `Titulo`, `Autor`, `Coautor`, `Tema o Materia`, `Series`, `Notas`, `Texto Ficha`, `Cota`, `ISBN`)
	VALUES (new.`ID`, new.`Titulo`, new.`Autor`, new.`Coautor`, new.`Tema o Materia`, new.`Series`, new.`Notas`, new.`Texto Ficha`, new.`Cota`, new.`ISBN`);
END;
--> statement-breakpoint
CREATE TRIGGER `trg_biblioteca_fts_ad` AFTER DELETE ON `Biblioteca` BEGIN
	INSERT INTO `biblioteca_fts`(`biblioteca_fts`, rowid, `Titulo`, `Autor`, `Coautor`, `Tema o Materia`, `Series`, `Notas`, `Texto Ficha`, `Cota`, `ISBN`)
	VALUES ('delete', old.`ID`, old.`Titulo`, old.`Autor`, old.`Coautor`, old.`Tema o Materia`, old.`Series`, old.`Notas`, old.`Texto Ficha`, old.`Cota`, old.`ISBN`);
END;
--> statement-breakpoint
CREATE TRIGGER `trg_biblioteca_fts_au` AFTER UPDATE ON `Biblioteca` BEGIN
	INSERT INTO `biblioteca_fts`(`biblioteca_fts`, rowid, `Titulo`, `Autor`, `Coautor`, `Tema o Materia`, `Series`, `Notas`, `Texto Ficha`, `Cota`, `ISBN`)
	VALUES ('delete', old.`ID`, old.`Titulo`, old.`Autor`, old.`Coautor`, old.`Tema o Materia`, old.`Series`, old.`Notas`, old.`Texto Ficha`, old.`Cota`, old.`ISBN`);
	INSERT INTO `biblioteca_fts`(rowid, `Titulo`, `Autor`, `Coautor`, `Tema o Materia`, `Series`, `Notas`, `Texto Ficha`, `Cota`, `ISBN`)
	VALUES (new.`ID`, new.`Titulo`, new.`Autor`, new.`Coautor`, new.`Tema o Materia`, new.`Series`, new.`Notas`, new.`Texto Ficha`, new.`Cota`, new.`ISBN`);
END;
--> statement-breakpoint
-- Reconstruccion idempotente del indice (cubre filas anteriores a esta migracion).
DELETE FROM `biblioteca_fts`;
--> statement-breakpoint
INSERT INTO `biblioteca_fts`(rowid, `Titulo`, `Autor`, `Coautor`, `Tema o Materia`, `Series`, `Notas`, `Texto Ficha`, `Cota`, `ISBN`)
	SELECT `ID`, `Titulo`, `Autor`, `Coautor`, `Tema o Materia`, `Series`, `Notas`, `Texto Ficha`, `Cota`, `ISBN` FROM `Biblioteca`;
