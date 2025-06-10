# SPDX-FileCopyrightText: (C) ColdFront Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django import forms
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404

from coldfront.core.allocation.models import (Allocation, 
                                              AllocationAccount,
                                              AllocationAttributeType,
                                              AllocationAttribute,
                                              AllocationStatusChoice,
                                              AllocationUserStorageStatusChoice,
                                              AllocationUserStoragePermissionChoice)
from coldfront.core.allocation.utils import get_user_resources
from coldfront.core.project.models import Project
from coldfront.core.resource.models import Resource, ResourceType
from coldfront.core.utils.common import import_from_settings

ALLOCATION_ACCOUNT_ENABLED = import_from_settings("ALLOCATION_ACCOUNT_ENABLED", False)
ALLOCATION_CHANGE_REQUEST_EXTENSION_DAYS = import_from_settings("ALLOCATION_CHANGE_REQUEST_EXTENSION_DAYS", [])


class AllocationForm(forms.Form):
    resource = forms.ModelChoiceField(queryset=None, empty_label=None)
    description = forms.CharField(required=False,
                                  max_length=512,
                                  help_text="""Enter a short description to describe this allocation.
                                            This is only used for display purposes to make allocations easier
                                            to identify.
                                            """,
                                  label="Short description"
                                  )
    folder_name = forms.CharField(required=False,
                                  max_length=64,
                                  validators=[
                                     RegexValidator(r'^[0-9a-zA-Z_-]*$', 'Only alphanumeric characters, underscores, and dashes are allowed.')
                                  ],
                                  help_text="Enter a folder name for your storage allocation"
                                  )
    justification = forms.CharField(widget=forms.Textarea)
    start_date = forms.DateField(
        label='Start Date',
        widget=forms.DateInput(attrs={'class': 'datepicker'}),
        required=True)
    end_date = forms.DateField(
        label='End Date',
        widget=forms.DateInput(attrs={'class': 'datepicker'}),
        required=True)
    cpu_hours = forms.IntegerField(required=True)
    gpu_hours = forms.IntegerField(required=True)
    memory_hours = forms.IntegerField(required=True)
    quantity = forms.IntegerField(required=True)
    storage_capacity = forms.IntegerField(required=True)
    storage_filecount = forms.IntegerField(required=True)
    allocation_account = forms.ChoiceField(required=False)

    def __init__(self, request_user, project_pk,  *args, **kwargs):
        super().__init__(*args, **kwargs)
        project_obj = get_object_or_404(Project, pk=project_pk)
        self.fields['resource'].queryset = get_user_resources(request_user).order_by(Lower("name"))

        self.fields['cpu_hours'].initial = 0
        self.fields['gpu_hours'].initial = 0
        self.fields['memory_hours'].initial = 0
        self.fields['storage_capacity'].initial = 0
        self.fields['storage_filecount'].initial = 0

        self.fields['quantity'].initial = 1

        if ALLOCATION_ACCOUNT_ENABLED:
            allocation_accounts = AllocationAccount.objects.filter(
                user=request_user)
            if allocation_accounts:
                self.fields['allocation_account'].choices = (((account.name, account.name))
                                                             for account in allocation_accounts)

            self.fields['allocation_account'].help_text = '<br/>Select account name to associate with resource. <a href="#Modal" id="modal_link">Click here to create an account name!</a>'
        else:
            self.fields['allocation_account'].widget = forms.HiddenInput()

        self.fields['justification'].help_text = '<br/>Justification for requesting this allocation.'

class AllocationUpdateForm(forms.Form):
    status = forms.ModelChoiceField(
        queryset=AllocationStatusChoice.objects.all().order_by(Lower("name")), empty_label=None
    )
    start_date = forms.DateField(
        label="Start Date", widget=forms.DateInput(attrs={"class": "datepicker"}), required=False
    )
    end_date = forms.DateField(label="End Date", widget=forms.DateInput(attrs={"class": "datepicker"}), required=False)
    description = forms.CharField(max_length=512, label="Description", required=False)
    is_locked = forms.BooleanField(required=False)
    is_changeable = forms.BooleanField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError("End date cannot be less than start date")


class AllocationInvoiceUpdateForm(forms.Form):
    status = forms.ModelChoiceField(
        queryset=AllocationStatusChoice.objects.filter(
            name__in=["Payment Pending", "Payment Requested", "Payment Declined", "Paid"]
        ).order_by(Lower("name")),
        empty_label=None,
    )


class AllocationAddUserForm(forms.Form):
    username = forms.CharField(max_length=150, disabled=True)
    first_name = forms.CharField(max_length=150, required=False, disabled=True)
    last_name = forms.CharField(max_length=150, required=False, disabled=True)
    email = forms.EmailField(max_length=100, required=False, disabled=True)
    selected = forms.BooleanField(initial=False, required=False)
    permissions = forms.ModelChoiceField(
        queryset=AllocationUserStoragePermissionChoice.objects.filter(~Q(name='None')), empty_label=None, required=False)
    
    def __init__(self, *args, **kwargs):
        init_username = None
        init_employeeType = None
        init_email = None
        has_email = False
        try:
            if 'initial' in kwargs:
                initial = kwargs.pop('initial')
                init_username = str(initial.pop('username')).strip()
                if 'email' in initial:
                    init_email = str(initial.pop('email')).strip()
                    if '@' in init_email:
                        has_email = True
                    
                kwargs['initial'] = initial
        except Exception as e:
            init_username = None

        disabledUser = False
        if init_username:
            try:
                eligible = has_email
                if get_user_model().objects.filter(username=init_username).exists():
                    userprofile = UserProfile.objects.get(user__username=init_username)
                    
                    for resource in get_user_resources(userprofile.user):
                        if resource.get_attribute('HasAccounts'):
                            user_sys_status, _ = UserSystemStatus.objects.get_or_create(user=userprofile.user, resource=resource)

                            if not (user_sys_status.system_eligibility.name == "Eligible" or user_sys_status.system_eligibility.name == "No Allocations"):
                                eligible = False
                                break
                else:
                    try:
                        if 'initial' in kwargs:
                            initial = kwargs.pop('initial')
                            init_employeeType=str(initial.pop('employeeType')).strip()
                            if SMU_EXT:
                                classification = checkResourceClassification(init_employeeType)
                                if classification == 'NA':
                                    eligible = False
                            kwargs['initial'] = initial
                    except Exception as e2:
                        logger.debug('failed to check classification: {}'.format(e))

                if not eligible:
                    init_username = init_username + ' (not HPC eligible)'
                    disabledUser = True
            except Exception as e:
                if 'UserProfile matching query does not exist' not in str(e):
                    logger.error("failed to check userprofile for {} with error {}".format(init_username, e))
        
        if init_username:
            self.declared_fields['username'].initial = init_username
        if init_email:
            self.declared_fields['email'].initial = init_email
        super(AllocationAddUserForm, self).__init__(*args, **kwargs)
        if disabledUser:
            self.fields['selected'].required = False
            self.fields['selected'].widget.attrs['disabled'] = 'disabled'
            self.fields['permissions'].required = False
            self.fields['permissions'].widget.attrs['disabled'] = 'disabled'


class AllocationRemoveUserForm(forms.Form):
    username = forms.CharField(max_length=150, disabled=True)
    first_name = forms.CharField(max_length=150, required=False, disabled=True)
    last_name = forms.CharField(max_length=150, required=False, disabled=True)
    email = forms.EmailField(max_length=100, required=False, disabled=True)
    selected = forms.BooleanField(initial=False, required=False)


class AllocationAttributeDeleteForm(forms.Form):
    pk = forms.IntegerField(required=False, disabled=True)
    name = forms.CharField(max_length=150, required=False, disabled=True)
    value = forms.CharField(max_length=150, required=False, disabled=True)
    selected = forms.BooleanField(initial=False, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pk"].widget = forms.HiddenInput()


class AllocationSearchForm(forms.Form):
    project = forms.CharField(label="Project Title", max_length=100, required=False)
    username = forms.CharField(label="Username", max_length=100, required=False)
    resource_type = forms.ModelChoiceField(
        label="Resource Type", queryset=ResourceType.objects.all().order_by(Lower("name")), required=False
    )
    resource_name = forms.ModelMultipleChoiceField(
        label="Resource Name",
        queryset=Resource.objects.filter(is_allocatable=True).order_by(Lower("name")),
        required=False,
    )
    allocation_attribute_name = forms.ModelChoiceField(
        label="Allocation Attribute Name",
        queryset=AllocationAttributeType.objects.all().order_by(Lower("name")),
        required=False,
    )
    allocation_attribute_value = forms.CharField(label="Allocation Attribute Value", max_length=100, required=False)
    end_date = forms.DateField(label="End Date", widget=forms.DateInput(attrs={"class": "datepicker"}), required=False)
    active_from_now_until_date = forms.DateField(
        label="Active from Now Until Date", widget=forms.DateInput(attrs={"class": "datepicker"}), required=False
    )
    status = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        queryset=AllocationStatusChoice.objects.all().order_by(Lower("name")),
        required=False,
    )
    show_all_allocations = forms.BooleanField(initial=False, required=False)


class AllocationReviewUserForm(forms.Form):
    ALLOCATION_REVIEW_USER_CHOICES = (
        ("keep_in_allocation_and_project", "Keep in allocation and project"),
        ("keep_in_project_only", "Remove from this allocation only"),
        ("remove_from_project", "Remove from project"),
    )

    username = forms.CharField(max_length=150, disabled=True)
    first_name = forms.CharField(max_length=150, required=False, disabled=True)
    last_name = forms.CharField(max_length=150, required=False, disabled=True)
    email = forms.EmailField(max_length=100, required=False, disabled=True)
    user_status = forms.ChoiceField(choices=ALLOCATION_REVIEW_USER_CHOICES)


class AllocationInvoiceNoteDeleteForm(forms.Form):
    pk = forms.IntegerField(required=False, disabled=True)
    note = forms.CharField(widget=forms.Textarea, disabled=True)
    author = forms.CharField(max_length=512, required=False, disabled=True)
    selected = forms.BooleanField(initial=False, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pk"].widget = forms.HiddenInput()


class AllocationAccountForm(forms.ModelForm):
    class Meta:
        model = AllocationAccount
        fields = [
            "name",
        ]


class AllocationAttributeChangeForm(forms.Form):
    pk = forms.IntegerField(required=False, disabled=True)
    name = forms.CharField(max_length=150, required=False, disabled=True)
    value = forms.CharField(max_length=150, required=False, disabled=True)
    new_value = forms.CharField(max_length=150, required=False, disabled=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pk"].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()

        if cleaned_data.get("new_value") != "":
            allocation_attribute = AllocationAttribute.objects.get(pk=cleaned_data.get("pk"))
            allocation_attribute.value = cleaned_data.get("new_value")
            allocation_attribute.clean()


class AllocationAttributeUpdateForm(forms.Form):
    change_pk = forms.IntegerField(required=False, disabled=True)
    attribute_pk = forms.IntegerField(required=False, disabled=True)
    name = forms.CharField(max_length=150, required=False, disabled=True)
    value = forms.CharField(max_length=150, required=False, disabled=True)
    new_value = forms.CharField(max_length=150, required=False, disabled=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["change_pk"].widget = forms.HiddenInput()
        self.fields["attribute_pk"].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        allocation_attribute = AllocationAttribute.objects.get(pk=cleaned_data.get("attribute_pk"))

        allocation_attribute.value = cleaned_data.get("new_value")
        allocation_attribute.clean()


class AllocationChangeForm(forms.Form):
    EXTENSION_CHOICES = [(0, "No Extension")]
    for choice in ALLOCATION_CHANGE_REQUEST_EXTENSION_DAYS:
        EXTENSION_CHOICES.append((choice, "{} days".format(choice)))

    end_date_extension = forms.TypedChoiceField(
        label="Request End Date Extension",
        choices=EXTENSION_CHOICES,
        coerce=int,
        required=False,
        empty_value=0,
    )
    justification = forms.CharField(
        label="Justification for Changes",
        widget=forms.Textarea,
        required=True,
        help_text="Justification for requesting this allocation change request.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class AllocationChangeNoteForm(forms.Form):
    notes = forms.CharField(
        max_length=512,
        label="Notes",
        required=False,
        widget=forms.Textarea,
        help_text="Leave any feedback about the allocation change request.",
    )


class AllocationAttributeCreateForm(forms.ModelForm):
    class Meta:
        model = AllocationAttribute
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super(AllocationAttributeCreateForm, self).__init__(*args, **kwargs)
        self.fields["allocation_attribute_type"].queryset = self.fields["allocation_attribute_type"].queryset.order_by(
            Lower("name")
        )

class AllocationPermissionChangeForm(forms.Form):
    username = forms.CharField(max_length=150, disabled=True)
    first_name = forms.CharField(max_length=150, required=False, disabled=True)
    last_name = forms.CharField(max_length=150, required=False, disabled=True)
    permissions = forms.ModelChoiceField(
        queryset=AllocationUserStoragePermissionChoice.objects.filter(~Q(name='None')), empty_label=None)