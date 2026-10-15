CREATE TABLE `Biblioteca` (
	`ID` integer PRIMARY KEY NOT NULL,
	`Cota` text,
	`Titulo` text,
	`Coautor` text,
	`Tema o Materia` text,
	`Series` text,
	`Paginas` text,
	`ISBN` text,
	`Notas` text,
	`Codigo CIDA` text,
	`Ejemplares` text,
	`Precio Unidad` text,
	`Precio Total` text,
	`Donacion` text,
	`Texto Ficha` text,
	`Autor` text,
	`Lujo/Rústico` text
);
--> statement-breakpoint
CREATE INDEX `idx_biblioteca_titulo` ON `Biblioteca` (`Titulo`);--> statement-breakpoint
CREATE INDEX `idx_biblioteca_autor` ON `Biblioteca` (`Autor`);--> statement-breakpoint
CREATE INDEX `idx_biblioteca_tema` ON `Biblioteca` (`Tema o Materia`);--> statement-breakpoint
CREATE INDEX `idx_biblioteca_texto_ficha` ON `Biblioteca` (`Texto Ficha`);--> statement-breakpoint
CREATE INDEX `idx_biblioteca_cota` ON `Biblioteca` (`Cota`);--> statement-breakpoint
CREATE INDEX `idx_biblioteca_isbn` ON `Biblioteca` (`ISBN`);