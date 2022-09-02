from django.core.paginator import Paginator

NUM_POST_ON_THE_PAGE = 10


def get_post_obj(request, post_list):
    paginator = Paginator(post_list, NUM_POST_ON_THE_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return page_obj
