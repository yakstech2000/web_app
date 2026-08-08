"""
Management command: reupload_images.py

Place this file at:
    product/management/commands/reupload_images.py

(You'll need to create the `management/` and `management/commands/` folders,
each with an empty `__init__.py`, if they don't already exist:

    product/
        management/
            __init__.py
            commands/
                __init__.py
                reupload_images.py

WHY THIS EXISTS
----------------
STORAGES was switched to Cloudinary at some point. Any records saved
*before* that switch have a file path stored in the DB (e.g.
"products/images/iphone_15pro.png") but the actual bytes were only ever
written to the local MEDIA_ROOT on disk -- never pushed to Cloudinary.
So Django happily builds a Cloudinary URL for a file that was never
uploaded there, and the <img> tag 404s.

This command walks every affected model/field, finds the matching file
still sitting in your local `media/` folder, and re-saves it through the
model field -- which forces it through whatever the *current* default
storage backend is (Cloudinary), actually uploading the bytes this time.

USAGE
-----
    python manage.py reupload_images                # do it for real
    python manage.py reupload_images --dry-run       # just report, no upload
    python manage.py reupload_images --model=product # only Product.* fields
    python manage.py reupload_images --model=category
    python manage.py reupload_images --model=review
    python manage.py reupload_images --model=receipt

Run --dry-run first. It will tell you exactly which files it found
locally and which DB records have no matching local file (those you'll
need to re-upload manually via admin, since the bytes are gone).
"""

import os

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from product.models import Product, Category, Review
from orders.models import Order


class Command(BaseCommand):
    help = "Re-upload locally-stored media files to the current default storage backend (Cloudinary)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Report what would happen without actually uploading anything.",
        )
        parser.add_argument(
            '--model',
            choices=['product', 'category', 'review', 'receipt', 'all'],
            default='all',
            help="Restrict the run to a single model's fields.",
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        which = options['model']

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no files will be uploaded.\n"))

        totals = {'uploaded': 0, 'skipped_missing': 0, 'skipped_empty': 0, 'errors': 0}

        if which in ('product', 'all'):
            self._process(
                Product.objects.all(),
                ['product_image', 'product_image_2', 'product_image_3'],
                dry_run, totals,
            )

        if which in ('category', 'all'):
            self._process(
                Category.objects.all(),
                ['image'],
                dry_run, totals,
            )

        if which in ('review', 'all'):
            self._process(
                Review.objects.all(),
                ['review_image'],
                dry_run, totals,
            )

        if which in ('receipt', 'all'):
            self._process(
                Order.objects.all(),
                ['payment_receipt'],
                dry_run, totals,
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. Uploaded: {totals['uploaded']}  "
            f"Missing locally: {totals['skipped_missing']}  "
            f"Empty field: {totals['skipped_empty']}  "
            f"Errors: {totals['errors']}"
        ))

        if totals['skipped_missing']:
            self.stdout.write(self.style.WARNING(
                "\nSome records had no matching local file — their original "
                "bytes are gone, so they'll need to be re-uploaded manually "
                "through the Django admin."
            ))

    def _process(self, queryset, field_names, dry_run, totals):
        model_name = queryset.model.__name__

        for instance in queryset:
            for field_name in field_names:
                field_file = getattr(instance, field_name)

                if not field_file:
                    totals['skipped_empty'] += 1
                    continue

                # field_file.name is the path as stored in the DB, e.g.
                # "products/images/iphone_15pro.png". We look for that
                # same relative path under the local MEDIA_ROOT.
                local_path = os.path.join(settings.MEDIA_ROOT, field_file.name)

                if not os.path.isfile(local_path):
                    self.stdout.write(self.style.ERROR(
                        f"[MISSING] {model_name} #{instance.pk} — {field_name}: "
                        f"no local file at {local_path}"
                    ))
                    totals['skipped_missing'] += 1
                    continue

                if dry_run:
                    self.stdout.write(
                        f"[WOULD UPLOAD] {model_name} #{instance.pk} — {field_name}: {local_path}"
                    )
                    totals['uploaded'] += 1
                    continue

                try:
                    with open(local_path, 'rb') as f:
                        file_bytes = f.read()

                    filename = os.path.basename(field_file.name)

                    # save=True writes to the DB too, but the field/model is
                    # already loaded and unchanged otherwise, so this is safe
                    # to call directly per-field.
                    field_file.save(filename, ContentFile(file_bytes), save=True)

                    self.stdout.write(self.style.SUCCESS(
                        f"[UPLOADED] {model_name} #{instance.pk} — {field_name}: {filename}"
                    ))
                    totals['uploaded'] += 1

                except Exception as exc:
                    self.stdout.write(self.style.ERROR(
                        f"[ERROR] {model_name} #{instance.pk} — {field_name}: {exc}"
                    ))
                    totals['errors'] += 1