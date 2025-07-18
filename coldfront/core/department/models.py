from django.db import models
from model_utils.models import TimeStampedModel

class Department(TimeStampedModel):
    """ A department represents academic units associated with a project.
        
    Attributes:
        name (str): department name from course catalog
        catalog_code (str): abbreviated code from course catalog
        academic_group (str): academic group (typically college level)
        academic_organization (str): academic organization (typically department level inside group)
    """
    class Meta:
        ordering = ['name']
        unique_together = ('name', 'catalog_code', 'academic_group', 'academic_organization')

    class DepartmentManager(models.Manager):
        def get_by_natural_key(self, name):
            return self.get(name=name)

    name = models.CharField(max_length=200)
    catalog_code = models.CharField(max_length=6)
    academic_group = models.CharField(max_length=200)
    academic_organization = models.CharField(max_length=200)
    objects = DepartmentManager()

    def __str__(self):
        return self.name + ' (' + self.academic_group + ')'

    def natural_key(self):
        return [self.name]
