from django.test import TestCase


class PostsViewTest(TestCase):
    def test_404(self):
        template = 'core/404.html'
        response = self.client.get('/nonexist-page/')
        self.assertTemplateUsed(response, template)
