from http import HTTPStatus

from django.test import TestCase, Client
from django.contrib.auth import get_user_model

from posts.models import Post, Group


User = get_user_model()


class PostsURLTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user = User.objects.create_user(username='auth')

        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test_slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
        )

    def setUp(self):
        # авторизированный
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        # автор
        self.author_client = Client()
        self.author_client.force_login(PostsURLTests.post.author)

    def test_create_page_for_authorized_client(self):
        """страницы для авторизованных"""
        template_list_OK_for_authorized = (
            '/',
            f'/group/{self.group.slug}/',
            f'/posts/{self.post.id}/',
            f'/profile/{self.post.author.username}/',
            '/create/',
        )
        for url in template_list_OK_for_authorized:
            with self.subTest(url=url):
                response = self.authorized_client.get(url)
                self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_edit_page_for_author_client(self):
        """страница edit доступна автору"""
        response = self.author_client.get(f'/posts/{self.post.id}/edit/')
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_over_pages_for_another(self):
        """страницы для не авторизированных"""
        template_list_OK_for_another = (
            '/',
            f'/group/{self.group.slug}/',
            f'/posts/{self.post.id}/',
            f'/profile/{self.post.author.username}/',
        )
        for url in template_list_OK_for_another:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_unexisting_page_return_404(self):
        """несущесвующая страница вернет 404 для всех"""
        response = self.client.get('/unexisting/')
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
