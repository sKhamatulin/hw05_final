import datetime


def year(request):
    year_today = (datetime.datetime.now().year)
    return {
        'year': year_today
    }
