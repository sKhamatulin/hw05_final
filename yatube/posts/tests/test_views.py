import shutil
import tempfile
from http import HTTPStatus

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django import forms
from django.shortcuts import get_object_or_404
from django.core.cache import cache

from posts.models import Post, Group, Follow

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostsViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(PostsViewTest, cls).setUpClass()

        cls.user = User.objects.create_user(username='auth')
        cls.follower = User.objects.create_user('fallower')
        # первая группа
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test_slug',
            description='Тестовое описание',
        )
        # второя группа
        cls.group2 = Group.objects.create(
            title='Тестовая группа2',
            slug='test_slug2',
            description='Тестовое описание2',
        )
        # загружаем картинку
        cls.small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        cls.uploaded = SimpleUploadedFile(
            name='small.gif',
            content=cls.small_gif,
            content_type='image/gif'
        )
        # первый пост (старше) ниже на странице индекс [1]
        cls.post = Post.objects.create(
            text='Тестовый пост',
            author=cls.user,
            group=cls.group,
            image=cls.uploaded,
        )
        # второй пост (моложе) выше на странице индекс [0]
        cls.post2 = Post.objects.create(
            text='Тестовый пост2',
            author=cls.user,
            group=cls.group2,
            image=cls.uploaded,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def check_obj_by_id(self, obj, obj_in_context):
        self.assertEqual(obj.id, obj_in_context.id)
        self.assertEqual(obj.text, obj_in_context.text)
        self.assertEqual(obj.author.username, obj_in_context.author.username)
        self.assertEqual(obj.group.title, obj_in_context.group.title)
        self.assertEqual(obj.image, obj_in_context.image)

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_follower = Client()
        self.authorized_client.force_login(self.user)
        self.authorized_follower.force_login(self.follower)
        self.kw_id = {'post_id': self.post.id}
        self.kw_user = {'username': self.user.username}
        self.kw_slug = {'slug': self.group.slug}
        self.kw_slug2 = {'slug': self.group2.slug}

    def test_fallowing(self):
        """юзер подписывается и отписываются от автора"""
        count = Follow.objects.count()
        self.authorized_follower.get(reverse('posts:profile_follow',
                                             kwargs=self.kw_user))
        self.assertEqual(Follow.objects.count(), count + 1)
        self.authorized_follower.get(reverse('posts:profile_unfollow',
                                             kwargs=self.kw_user))
        self.assertEqual(Follow.objects.count(), 0)

    def test_page_follow(self):
        """на странице fallow появляются
        посты авторов на которых подписан юзер"""
        Follow.objects.create(user=self.follower,
                              author=self.user)
        response = self.authorized_follower.get('/follow/')
        obj = get_object_or_404(Post, pk=self.post2.id)
        obj_in_context = response.context['page_obj'][0]
        self.check_obj_by_id(obj, obj_in_context)

    def test_page_follow_not_equal(self):
        """на странице fallow не появляются
        посты авторов на которых не подписан юзер"""
        Follow.objects.create(user=self.follower,
                              author=self.user)
        response = self.authorized_client.get('/follow/')
        obj_in_context = response.context['page_obj']
        self.assertEqual(len(obj_in_context), 0)

    def test_pages_uses_correct_template(self):
        """ожидаемые шаблоны"""
        cache.clear()
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_list', kwargs=self.kw_slug):
            'posts/group_list.html',
            reverse('posts:profile', kwargs=self.kw_user):
            'posts/profile.html',
            reverse('posts:post_detail', kwargs=self.kw_id):
            'posts/post_detail.html',
            reverse('posts:post_create'): 'posts/create_post.html',
            reverse('posts:post_edit', kwargs=self.kw_id):
            'posts/create_post.html',
        }
        for reverse_name, template, in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_index_page_show_correct_context(self):
        """ожидаемый контекст для index"""
        cache.clear()
        response = self.authorized_client.get(reverse('posts:index'))
        obj = get_object_or_404(Post, pk=self.post.id)
        obj_in_context = response.context['page_obj'][1]
        self.check_obj_by_id(obj, obj_in_context)

    def test_group_list_page_show_correct_context(self):
        """ожидаемый контекст для group list"""
        response = self.authorized_client.get(reverse(
                                              'posts:group_list',
                                              kwargs=self.kw_slug2))
        obj = get_object_or_404(Post, pk=self.post2.id)
        obj_in_context = response.context['page_obj'][0]
        self.check_obj_by_id(obj, obj_in_context)

    def test_group_list_no_second_post(self):
        """пост перовой группы не попал в посты второй группы"""
        response = self.authorized_client.get(reverse('posts:group_list',
                                                      kwargs=self.kw_slug))
        with self.assertRaises(IndexError):
            second_obj = response.context['page_obj'][1]
            self.assertEqual(second_obj, None)

    def test_profile_page_show_correct_context(self):
        """ожидаемый контекст для profile list"""
        response = self.authorized_client.get(reverse('posts:profile',
                                                      kwargs=self.kw_user))
        obj = get_object_or_404(Post, pk=self.post.id)
        obj_in_context = response.context['page_obj'][1]
        self.check_obj_by_id(obj, obj_in_context)

    def test_post_detail_pages_show_correct_context(self):
        """ожидаемый контекст для post detail"""
        response = (self.authorized_client.
                    get(reverse('posts:post_detail', kwargs=self.kw_id)))
        obj = get_object_or_404(Post, pk=self.post.id)
        obj_in_context = response.context.get('post')
        self.check_obj_by_id(obj, obj_in_context)

    def test_create_post(self):
        """Комментарий оставляет авторизованный пользователь"""
        response = self.authorized_client.get(reverse('posts:add_comment',
                                                      kwargs=self.kw_id))
        self.assertEqual(response.status_code, HTTPStatus.FOUND)

    def test_create_page_show_correct_context(self):
        """ожидаемая форма для create"""
        response = self.authorized_client.get(reverse('posts:post_create'))
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_edit_page_show_correct_context(self):
        """ожидаемая форма для edit"""
        response = self.authorized_client.get(reverse('posts:post_edit',
                                                      kwargs=self.kw_id))
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test_slug',
            description='Тестовое описание',
        )
        for i in range(0, 13, 1):
            cls.post = Post.objects.create(
                text=f'Тестовая пост номер {i}',
                author=cls.user,
                group=cls.group)

    def setUp(self):
        self.kw_user = {'username': self.user.username}
        self.kw_slug = {'slug': self.group.slug}

    def test_first_page_index_contains_ten_records(self):
        """на первой странице index 10 постов"""
        cache.clear()
        response = self.client.get(reverse('posts:index'))
        self.assertEqual(len(response.context['page_obj']), 10)

    def test_second_page_index_contains_three_records(self):
        """на второй странице index 3 поста"""
        response = self.client.get(reverse('posts:index') + '?page=2')
        self.assertEqual(len(response.context['page_obj']), 3)

    def test_first_page_group_list_contains_ten_records(self):
        """на первой странице group list 10 постов"""
        response = self.client.get(reverse('posts:group_list',
                                           kwargs=self.kw_slug))
        self.assertEqual(len(response.context['page_obj']), 10)

    def test_second_page_group_list_contains_three_records(self):
        """на второй странице group list 3 поста"""
        response = self.client.get(reverse('posts:group_list',
                                           kwargs=self.kw_slug) + '?page=2')
        self.assertEqual(len(response.context['page_obj']), 3)

    def test_first_page_profile_contains_ten_records(self):
        """на первой странице profile list 10 постов"""
        response = self.client.get(reverse('posts:profile',
                                           kwargs=self.kw_user))
        self.assertEqual(len(response.context['page_obj']), 10)

    def test_second_page_profile_contains_three_records(self):
        """на второй странице profile list 3 поста"""
        response = self.client.get(reverse('posts:profile',
                                           kwargs=self.kw_user) + '?page=2')
        self.assertEqual(len(response.context['page_obj']), 3)
