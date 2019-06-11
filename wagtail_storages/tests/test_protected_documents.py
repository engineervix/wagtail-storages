from urllib.parse import urlparse

from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from wagtail.core.models import Collection

from ..factories import CollectionViewRestrictionFactory, DocumentFactory


class AmazonS3DocumentTests(TestCase):
    def check_s3_url(self, url):
        return 's3.amazonaws.com' in url

    def check_url_signed(self, url):
        parsed_url = urlparse(url)
        query_args = [
            'AWSAccessKeyId',
            'Signature',
            'Expires',
        ]
        for query_arg in query_args:
            if query_arg not in parsed_url.query:
                return False
        return True

    def setUp(self):
        self.client = Client()
        self.root_collection = Collection.get_first_root_node()
        self.private_collection = self.root_collection.add_child(
            name='Restricted collection',
        )
        self.private_collection_restriction = CollectionViewRestrictionFactory(collection=self.private_collection)
        self.view_restriction_session_key = self.private_collection_restriction.passed_view_restrictions_session_key

    def test_create_public_document(self):
        # Create document.
        document = DocumentFactory()

        # Check the document is on amazon's servers.
        self.assertTrue(self.check_s3_url(document.file.url))

        # Load the document
        url = reverse('wagtaildocs_serve', args=(document.id, document.filename))
        response = self.client.get(url)

        # Test wagtail redirects to S3.
        self.assertEquals(response.status_code, 302)
        self.assertTrue(response.url)
        # Check the url given wasn't signed.
        self.assertFalse(self.check_url_signed(response.url))

    def test_create_private_document(self):
        # Create document.
        document = DocumentFactory()
        # Add the document to the private collection.
        document.collection = self.private_collection
        document.save()

        # Check the document is on amazon's servers.
        self.assertTrue(self.check_s3_url(document.file.url))

        # Authorise the session.
        s = self.client.session
        s.update({
            self.view_restriction_session_key: [self.private_collection_restriction.id],
        })
        s.save()

        # Load the document
        url = reverse('wagtaildocs_serve', args=(document.id, document.filename))
        response = self.client.get(url)

        # Test wagtail redirects to S3.
        self.assertEquals(response.status_code, 302)
        self.assertTrue(response.url)
        # Check the url given was signed.
        self.assertTrue(self.check_url_signed(response.url))
