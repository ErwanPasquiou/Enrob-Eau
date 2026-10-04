-- Stockage local du prototype : deux tables vides, contenu binaire natif.
CREATE TABLE IF NOT EXISTS PhotoDemande (
    PhotoReference TEXT PRIMARY KEY,
    RequestReference TEXT NOT NULL,
    PhotoName TEXT NOT NULL,
    FileName TEXT NOT NULL,
    MimeType TEXT NOT NULL,
    SizeBytes INTEGER NOT NULL,
    Content BLOB NOT NULL,
    Caption TEXT NOT NULL DEFAULT '',
    CreatedBy TEXT NOT NULL,
    CreatedAt TEXT NOT NULL,
    UpdatedAt TEXT NOT NULL,
    Version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_photo_demande ON PhotoDemande(RequestReference);
CREATE TABLE IF NOT EXISTS PhotoPrestation (
    PhotoReference TEXT PRIMARY KEY,
    ServiceReference TEXT NOT NULL,
    PhotoName TEXT NOT NULL,
    FileName TEXT NOT NULL,
    MimeType TEXT NOT NULL,
    SizeBytes INTEGER NOT NULL,
    Content BLOB NOT NULL,
    Caption TEXT NOT NULL DEFAULT '',
    CreatedBy TEXT NOT NULL,
    CreatedAt TEXT NOT NULL,
    UpdatedAt TEXT NOT NULL,
    Version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_photo_prestation ON PhotoPrestation(ServiceReference);
