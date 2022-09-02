import shutil
import tempfile
from http import HTTPStatus
from tkinter import N

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django import forms
from django.shortcuts import get_object_or_404
from django.core.cache import cache

from posts.models import Post, Group, Follow, Comment
from posts.utils import NUM_POST_ON_THE_PAGE

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostsViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(PostsViewTest, cls).setUpClass()

        cls.user = User.objects.create_user(username='auth')
        cls.follower = User.objects.create_user('follower')
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
        cls.kw_id = {'post_id': cls.post.id}
        cls.kw_user = {'username': cls.user.username}
        cls.kw_slug = {'slug': cls.group.slug}
        cls.kw_slug2 = {'slug': cls.group2.slug}

        cls.form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField
        }

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

    def test_following(self):
        """юзер подписывается на автора"""
        count = Follow.objects.count()
        self.authorized_follower.get(reverse('posts:profile_follow',
                                             kwargs=self.kw_user))
        self.assertEqual(Follow.objects.count(), count + 1)
    
    def test_unfollowing(self):
        """юзер подписывается и отписывается от автора"""
        count = Follow.objects.count()
        self.authorized_follower.get(reverse('posts:profile_follow',
                                             kwargs=self.kw_user))
        self.assertEqual(Follow.objects.count(), count + 1)
        self.authorized_follower.get(reverse('posts:profile_unfollow',
                                             kwargs=self.kw_user))
        self.assertEqual(Follow.objects.count(), 0)

    def test_page_follow(self):
        """на странице follow появляются
        посты авторов на которых подписан юзер"""
        Follow.objects.create(user=self.follower,
                              author=self.user)
        response = self.authorized_follower.get('/follow/')
        obj = get_object_or_404(Post, pk=self.post2.id)
        obj_in_context = response.context['page_obj'][0]
        self.check_obj_by_id(obj, obj_in_context)

    def test_page_follow_not_equal(self):
        """на странице follow не появляются
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
        Comment.objects.create(post=self.post,
                               author=self.user,
                               text='Тестовый коммент')
        response = self.authorized_client.get(reverse('posts:add_comment',
                                                      kwargs=self.kw_id))
        obj = get_object_or_404(Comment)
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(obj.text, 'Тестовый коммент')

    def test_create_post(self):
        """Комментарий оставляет не авторизованный пользователь"""
        with self.assertRaises(ValueError):
            comment = Comment.objects.create(post=self.post,
                                             author=self.client,
                                             text='Тестовый коммент')
            self.assertEqual(comment, None)

    def test_create_page_show_correct_context(self):
        """ожидаемая форма для create"""
        response = self.authorized_client.get(reverse('posts:post_create'))
        for value, expected in self.form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_edit_page_show_correct_context(self):
        """ожидаемая форма для edit"""
        response = self.authorized_client.get(reverse('posts:post_edit',
                                                      kwargs=self.kw_id))
        for value, expected in self.form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)
    
    def test_cache_index_page(self):
        """тест каэша на странице"""
        post_for_cache = Post.objects.create(
            author=self.user,
            group=self.group,
            text='Тестовый пост для проверки кэша'
        )
        response = self.authorized_client.get(reverse('posts:index'))
        post_for_cache.delete()
        response_cached = self.authorized_client.get(reverse('posts:index'))
        cache.clear()
        response_cleared = self.authorized_client.get(reverse('posts:index'))

        self.assertEqual(response.content, response_cached.content)
        self.assertNotEqual(response_cached.content, response_cleared.content)


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
        cls.NUM_POST_FOR_TESTS = NUM_POST_ON_THE_PAGE + 3
        cls.NUM_POST_ON_THE_SECOND_PAGE = (cls.NUM_POST_FOR_TESTS
                                           % NUM_POST_ON_THE_PAGE)
        cls.kw_user = {'username': cls.user.username}
        cls.kw_slug = {'slug': cls.group.slug}

        posts = [
            Post(
                author=cls.user,
                text=f'Тестовая пост номер {i}',
                group=cls.group,
            ) for i in range(0, cls.NUM_POST_FOR_TESTS, 1)
        ]
        Post.objects.bulk_create(posts)

    def test_first_pages_paginator(self):
        """на первых страницах 10 постов"""
        cache.clear()
        response_first_pages = [
            self.client.get(reverse('posts:index')),
            self.client.get(reverse('posts:group_list',
                            kwargs=self.kw_slug)),
            self.client.get(reverse('posts:profile',
                            kwargs=self.kw_user))
        ]
        for response in response_first_pages:
            self.assertEqual(len(response.context['page_obj']),
                             NUM_POST_ON_THE_PAGE)

    def test_second_pages_paginator(self):
        """на вторых страницах 3 поста"""
        cache.clear()
        response_first_pages = [
            self.client.get(reverse('posts:index') + '?page=2'),
            self.client.get(reverse('posts:group_list',
                            kwargs=self.kw_slug) + '?page=2'),
            self.client.get(reverse('posts:profile',
                            kwargs=self.kw_user) + '?page=2')
        ]
        for response in response_first_pages:
            self.assertEqual(len(response.context['page_obj']),
                             self.NUM_POST_ON_THE_SECOND_PAGE)
