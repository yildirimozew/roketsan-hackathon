import json


def load_reports(file_path):
    """
    JSON dosyasındaki saha raporlarını yükler.
    """

    with open(file_path, "r", encoding="utf-8") as file:
        reports = json.load(file)

    return reports


def get_reports_by_region(reports, region):
    """
    Yalnızca belirtilen bölgeye ait raporları döndürür.
    """

    relevant_reports = []

    for report in reports:

        if report["region"] == region:
            relevant_reports.append(report)

    return relevant_reports