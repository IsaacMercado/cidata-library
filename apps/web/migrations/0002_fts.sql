-- Full-text search with FTS5 over Biblioteca.
-- The virtual table does NOT duplicate content (content= points to Biblioteca)
-- and triggers keep it in sync on INSERT/UPDATE/DELETE.
-- unicode61 with remove_diacritics=2: case- and accent-insensitive
-- (rustico matches "Rústico"), suitable for Spanish text.

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
