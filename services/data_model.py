"""Modèle métier du diagramme Enrob'Eau (hors photos)."""
SCHEMAS = {
    "demandes": "RequestReference RequestDate RequesterReference ReportedAdress ReportedCity AffectedStreets LocationLandmark CustomerName BusinessDomain LeakReportReference RequestReason MeterReference ReportedMaterial ReportedDiameter ReportedRoadType ReportedRoadTypeOther ReportedSurfaceType RoadImpact EstimatedWorkDays DictAtuIndicator WaterShutdownIndicator SafetyInstructions SpecialConditions RequestComment ImpactTransport RequestStatus CreatedAt UpdatedAt".split(),
    "interventions": "WorkOrderReferenceEnrobEau WorkOrderReferenceSaur RequestReference IssuedAt ReceivedAt ClosedAt SaurComment CityWorksComment CityInformedAt CustomerWorksComment CustomerInformedAt WorkOrderStatus CreatedAt UpdatedAt".split(),
    "prestations": "ServiceReference WorkOrderReferenceEnrobEau ServiceCode WorkAddress WorkCity WorkCoordinates WorkReason SurfaceRepairType RoadType Comment ExcavationDate BackfillDate Concrete2CmDate HasConcrete2Cm TemporaryRepairDate HasTemporaryRepair FinalRepairDate ServiceStatus CreatedAt UpdatedAt".split(),
}
LABELS = {
    "RequestReference": "Référence de la demande", "RequestDate": "Date de la demande",
    "RequesterReference": "E-mail du demandeur", "ReportedAdress": "Adresse signalée",
    "ReportedCity": "Commune signalée", "AffectedStreets": "Rues concernées",
    "LocationLandmark": "Repère de localisation", "CustomerName": "Nom du client",
    "BusinessDomain": "Domaine d'activité", "LeakReportReference": "Référence de la fiche fuite",
    "RequestReason": "Motif de la demande", "ReportedMaterial": "Matériau signalé",
    "MeterReference": "Matricule Compteur", "ReportedRoadTypeOther": "Précision du type de voirie",
    "ReportedDiameter": "Diamètre signalé", "ReportedRoadType": "Type de voirie signalé",
    "ReportedSurfaceType": "Revêtement signalé", "RoadImpact": "Impact sur la voirie",
    "EstimatedWorkDays": "Durée estimée des travaux (jours)", "DictAtuIndicator": "DICT / ATU",
    "WaterShutdownIndicator": "Coupure d'eau", "SafetyInstructions": "Consignes de sécurité",
    "SpecialConditions": "Conditions particulières", "RequestComment": "Commentaire de la demande",
    "ImpactTransport": "Impact sur les transports", "RequestStatus": "Statut de la demande",
    "CreatedAt": "Créé le", "UpdatedAt": "Mis à jour le", "WorkOrderReferenceEnrobEau": "Identifiant technique de l'intervention",
    "WorkOrderReferenceSaur": "Référence de l'intervention SI SAUR",
    "IssuedAt": "DICT / ATU émise le", "ReceivedAt": "DICT / ATU reçue le", "ClosedAt": "Date de clôture de l'intervention",
    "SaurComment": "Commentaire SAUR", "CityWorksComment": "Commentaire travaux commune",
    "CityInformedAt": "Commune informée le", "CustomerWorksComment": "Commentaire travaux abonnés",
    "CustomerInformedAt": "Abonnés informés le", "WorkOrderStatus": "Statut de l'intervention",
    "ServiceReference": "Référence de la prestation", "ServiceCode": "Code prestation",
    "WorkAddress": "Adresse des travaux", "WorkCity": "Commune des travaux",
    "WorkCoordinates": "Coordonnées des travaux", "WorkReason": "Motif des travaux",
    "SurfaceRepairType": "Type de réfection de surface", "RoadType": "Type de voirie",
    "Comment": "Commentaire", "ExcavationDate": "Date de terrassement", "BackfillDate": "Date de remblaiement",
    "Concrete2CmDate": "Date du béton 2 cm", "HasConcrete2Cm": "Béton 2 cm réalisé",
    "TemporaryRepairDate": "Date de réfection provisoire", "HasTemporaryRepair": "Réfection provisoire réalisée",
    "FinalRepairDate": "Date de réfection définitive", "ServiceStatus": "Statut de la prestation",
}
DATE_FIELDS = {field for fields in SCHEMAS.values() for field in fields if field.endswith("Date") or field.endswith("At")}
BOOL_FIELDS = {"ImpactTransport", "HasConcrete2Cm", "HasTemporaryRepair"}
