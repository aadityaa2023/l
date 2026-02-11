"""
Feature Settings Views for Platform Admin
Handles Footer Settings and Page Content management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from apps.platformadmin.decorators import platformadmin_required
from apps.platformadmin.models import FooterSettings, PageContent
from apps.platformadmin.forms import FooterSettingsForm, PageContentForm
from apps.platformadmin.utils import ActivityLog





# ============================================================================
# FOOTER SETTINGS MANAGEMENT
# ============================================================================

@login_required
@platformadmin_required
def footer_settings(request):
    """Manage footer settings (singleton)"""
    settings = FooterSettings.get_settings()
    
    if request.method == 'POST':
        form = FooterSettingsForm(request.POST)
        if form.is_valid():
            # Store old values for logging
            old_values = {
                'company_name': settings.company_name,
                'copyright_text': settings.copyright_text
            }
            
            # Update all fields
            settings.company_name = form.cleaned_data['company_name']
            settings.company_description = form.cleaned_data.get('company_description', '')
            settings.contact_email = form.cleaned_data.get('contact_email', '')
            settings.contact_phone = form.cleaned_data.get('contact_phone', '')
            settings.contact_address = form.cleaned_data.get('contact_address', '')
            settings.facebook_url = form.cleaned_data.get('facebook_url', '')
            settings.twitter_url = form.cleaned_data.get('twitter_url', '')
            settings.instagram_url = form.cleaned_data.get('instagram_url', '')
            settings.linkedin_url = form.cleaned_data.get('linkedin_url', '')
            settings.youtube_url = form.cleaned_data.get('youtube_url', '')
            settings.github_url = form.cleaned_data.get('github_url', '')
            settings.copyright_text = form.cleaned_data['copyright_text']
            settings.privacy_policy_url = form.cleaned_data.get('privacy_policy_url', '')
            settings.terms_of_service_url = form.cleaned_data.get('terms_of_service_url', '')
            settings.show_newsletter_signup = form.cleaned_data.get('show_newsletter_signup', True)
            settings.newsletter_heading = form.cleaned_data['newsletter_heading']
            settings.newsletter_description = form.cleaned_data.get('newsletter_description', '')
            settings.updated_by = request.user
            settings.save()
            
            # Log the action
            ActivityLog.log_action(
                request.user,
                'update',
                'FooterSettings',
                '1',
                'Footer Settings',
                old_values=old_values,
                new_values={'company_name': settings.company_name, 'copyright_text': settings.copyright_text}
            )
            
            messages.success(request, 'Footer settings updated successfully!')
            return redirect('platformadmin:footer_settings')
    else:
        # Pre-populate form with existing data
        initial_data = {
            'company_name': settings.company_name,
            'company_description': settings.company_description,
            'contact_email': settings.contact_email,
            'contact_phone': settings.contact_phone,
            'contact_address': settings.contact_address,
            'facebook_url': settings.facebook_url,
            'twitter_url': settings.twitter_url,
            'instagram_url': settings.instagram_url,
            'linkedin_url': settings.linkedin_url,
            'youtube_url': settings.youtube_url,
            'github_url': settings.github_url,
            'copyright_text': settings.copyright_text,
            'privacy_policy_url': settings.privacy_policy_url,
            'terms_of_service_url': settings.terms_of_service_url,
            'show_newsletter_signup': settings.show_newsletter_signup,
            'newsletter_heading': settings.newsletter_heading,
            'newsletter_description': settings.newsletter_description,
        }
        form = FooterSettingsForm(initial=initial_data)
    
    context = {
        'form': form,
        'settings': settings
    }
    return render(request, 'platformadmin/feature_settings/footer_settings.html', context)


# ============================================================================
# PAGE CONTENT MANAGEMENT
# ============================================================================

@login_required
@platformadmin_required
def page_content_list(request):
    """List all page contents"""
    pages = PageContent.objects.all().order_by('display_order', 'title')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        pages = pages.filter(status=status_filter)
    
    # Filter by page type
    page_type_filter = request.GET.get('page_type')
    if page_type_filter:
        pages = pages.filter(page_type=page_type_filter)
    
    # Search
    search_query = request.GET.get('search')
    if search_query:
        pages = pages.filter(
            Q(title__icontains=search_query) |
            Q(slug__icontains=search_query) |
            Q(content__icontains=search_query)
        )
    
    context = {
        'pages': pages,
        'status_filter': status_filter,
        'page_type_filter': page_type_filter,
        'search_query': search_query,
    }
    return render(request, 'platformadmin/feature_settings/page_content_list.html', context)


@login_required
@platformadmin_required
def page_content_create(request):
    """Create a new page content"""
    if request.method == 'POST':
        form = PageContentForm(request.POST, request.FILES)
        if form.is_valid():
            page = PageContent.objects.create(
                page_type=form.cleaned_data['page_type'],
                title=form.cleaned_data['title'],
                slug=form.cleaned_data['slug'],
                hero_title=form.cleaned_data.get('hero_title', ''),
                hero_subtitle=form.cleaned_data.get('hero_subtitle', ''),
                content=form.cleaned_data['content'],
                meta_title=form.cleaned_data.get('meta_title', ''),
                meta_description=form.cleaned_data.get('meta_description', ''),
                meta_keywords=form.cleaned_data.get('meta_keywords', ''),
                status=form.cleaned_data['status'],
                show_in_footer=form.cleaned_data.get('show_in_footer', True),
                show_in_header=form.cleaned_data.get('show_in_header', False),
                display_order=form.cleaned_data['display_order'],
                created_by=request.user,
                updated_by=request.user
            )
            
            # Handle hero image if provided
            if 'hero_image' in request.FILES:
                page.hero_image = form.cleaned_data['hero_image']
                page.save()
            
            # Log the action
            ActivityLog.log_action(
                request.user,
                'create',
                'PageContent',
                str(page.id),
                page.title,
                new_values={'title': page.title, 'page_type': page.page_type}
            )
            
            messages.success(request, f'Page "{page.title}" created successfully!')
            return redirect('platformadmin:footer_settings')
    else:
        form = PageContentForm()
    
    context = {'form': form}
    return render(request, 'platformadmin/feature_settings/page_content_form.html', context)


@login_required
@platformadmin_required
def page_content_edit(request, page_id):
    """Edit an existing page content"""
    page = get_object_or_404(PageContent, id=page_id)
    
    if request.method == 'POST':
        form = PageContentForm(request.POST, request.FILES)
        if form.is_valid():
            # Store old values for logging
            old_values = {
                'title': page.title,
                'status': page.status
            }
            
            # Update fields
            page.page_type = form.cleaned_data['page_type']
            page.title = form.cleaned_data['title']
            page.slug = form.cleaned_data['slug']
            page.hero_title = form.cleaned_data.get('hero_title', '')
            page.hero_subtitle = form.cleaned_data.get('hero_subtitle', '')
            page.content = form.cleaned_data['content']
            page.meta_title = form.cleaned_data.get('meta_title', '')
            page.meta_description = form.cleaned_data.get('meta_description', '')
            page.meta_keywords = form.cleaned_data.get('meta_keywords', '')
            page.status = form.cleaned_data['status']
            page.show_in_footer = form.cleaned_data.get('show_in_footer', True)
            page.show_in_header = form.cleaned_data.get('show_in_header', False)
            page.display_order = form.cleaned_data['display_order']
            page.updated_by = request.user
            
            # Update hero image if provided
            if 'hero_image' in request.FILES:
                page.hero_image = form.cleaned_data['hero_image']
            
            page.save()
            
            # Log the action
            ActivityLog.log_action(
                request.user,
                'update',
                'PageContent',
                str(page.id),
                page.title,
                old_values=old_values,
                new_values={'title': page.title, 'status': page.status}
            )
            
            messages.success(request, f'Page "{page.title}" updated successfully!')
            return redirect('platformadmin:footer_settings')
    else:
        # Pre-populate form with existing data
        initial_data = {
            'page_type': page.page_type,
            'title': page.title,
            'slug': page.slug,
            'hero_title': page.hero_title,
            'hero_subtitle': page.hero_subtitle,
            'content': page.content,
            'meta_title': page.meta_title,
            'meta_description': page.meta_description,
            'meta_keywords': page.meta_keywords,
            'status': page.status,
            'show_in_footer': page.show_in_footer,
            'show_in_header': page.show_in_header,
            'display_order': page.display_order,
        }
        form = PageContentForm(initial=initial_data)
    
    context = {
        'form': form,
        'page': page,
        'is_edit': True
    }
    return render(request, 'platformadmin/feature_settings/page_content_form.html', context)


@login_required
@platformadmin_required
def page_content_delete(request, page_id):
    """Delete a page content"""
    page = get_object_or_404(PageContent, id=page_id)
    
    if request.method == 'POST':
        title = page.title
        
        # Log the action before deletion
        ActivityLog.log_action(
            request.user,
            'delete',
            'PageContent',
            str(page.id),
            title,
            old_values={'title': title, 'page_type': page.page_type}
        )
        
        page.delete()
        messages.success(request, f'Page "{title}" deleted successfully!')
        return redirect('platformadmin:footer_settings')
    
    context = {'page': page}
    return render(request, 'platformadmin/feature_settings/page_content_confirm_delete.html', context)
