// Ocean-themed Profile Page JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Profile Information Edit Toggle
    const editProfileBtn = document.getElementById('edit-profile-btn');
    const cancelEditBtn = document.getElementById('cancel-edit-btn');
    const profileForm = document.getElementById('profile-form');
    const profileActions = document.getElementById('profile-actions');
    
    if (editProfileBtn) {
        editProfileBtn.addEventListener('click', function() {
            toggleFormEditing(profileForm, true);
            profileActions.style.display = 'flex';
            this.style.display = 'none';
        });
    }
    
    if (cancelEditBtn) {
        cancelEditBtn.addEventListener('click', function() {
            toggleFormEditing(profileForm, false);
            profileActions.style.display = 'none';
            editProfileBtn.style.display = 'block';
        });
    }
    
    // Research Interests Edit Toggle
    const editInterestsBtn = document.getElementById('edit-interests-btn');
    const cancelInterestsBtn = document.getElementById('cancel-interests-btn');
    const interestsForm = document.getElementById('interests-form');
    const interestsActions = document.getElementById('interests-actions');
    const addAreaGroup = document.getElementById('add-area-group');
    const addSpeciesGroup = document.getElementById('add-species-group');
    const addMethodGroup = document.getElementById('add-method-group');
    
    if (editInterestsBtn) {
        editInterestsBtn.addEventListener('click', function() {
            toggleFormEditing(interestsForm, true);
            interestsActions.style.display = 'flex';
            addAreaGroup.style.display = 'flex';
            addSpeciesGroup.style.display = 'flex';
            addMethodGroup.style.display = 'flex';
            this.style.display = 'none';
        });
    }
    
    if (cancelInterestsBtn) {
        cancelInterestsBtn.addEventListener('click', function() {
            toggleFormEditing(interestsForm, false);
            interestsActions.style.display = 'none';
            addAreaGroup.style.display = 'none';
            addSpeciesGroup.style.display = 'none';
            addMethodGroup.style.display = 'none';
            editInterestsBtn.style.display = 'block';
        });
    }
    
    // Add Research Area Tag
    const addAreaBtn = document.getElementById('add-area-btn');
    const newAreaInput = document.getElementById('new-area');
    const researchTags = document.querySelector('.research-tags');
    
    if (addAreaBtn && newAreaInput && researchTags) {
        addAreaBtn.addEventListener('click', function() {
            addTag(newAreaInput, researchTags, 'bg-primary');
        });
    }
    
    // Add Species Tag
    const addSpeciesBtn = document.getElementById('add-species-btn');
    const newSpeciesInput = document.getElementById('new-species');
    const speciesTags = document.querySelector('.species-tags');
    
    if (addSpeciesBtn && newSpeciesInput && speciesTags) {
        addSpeciesBtn.addEventListener('click', function() {
            addTag(newSpeciesInput, speciesTags, 'bg-info');
        });
    }
    
    // Add Method Tag
    const addMethodBtn = document.getElementById('add-method-btn');
    const newMethodInput = document.getElementById('new-method');
    const methodsTags = document.querySelector('.methods-tags');
    
    if (addMethodBtn && newMethodInput && methodsTags) {
        addMethodBtn.addEventListener('click', function() {
            addTag(newMethodInput, methodsTags, 'bg-success');
        });
    }
    
    // Publication Abstract Toggle
    const abstractToggles = document.querySelectorAll('.toggle-abstract');
    abstractToggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const icon = this.querySelector('i');
            if (icon.classList.contains('fa-chevron-down')) {
                icon.classList.replace('fa-chevron-down', 'fa-chevron-up');
                this.innerHTML = this.innerHTML.replace('Show Abstract', 'Hide Abstract');
            } else {
                icon.classList.replace('fa-chevron-up', 'fa-chevron-down');
                this.innerHTML = this.innerHTML.replace('Hide Abstract', 'Show Abstract');
            }
        });
    });
    
    // Add Publication Button
    const addPublicationBtn = document.getElementById('add-publication-btn');
    const firstPublicationBtn = document.getElementById('first-publication-btn');
    
    if (addPublicationBtn) {
        addPublicationBtn.addEventListener('click', function() {
            showPublicationModal();
        });
    }
    
    if (firstPublicationBtn) {
        firstPublicationBtn.addEventListener('click', function() {
            showPublicationModal();
        });
    }
    
    // Add Education Button
    const addEducationBtn = document.getElementById('add-education-btn');
    const firstEducationBtn = document.getElementById('first-education-btn');
    
    if (addEducationBtn) {
        addEducationBtn.addEventListener('click', function() {
            showEducationModal();
        });
    }
    
    if (firstEducationBtn) {
        firstEducationBtn.addEventListener('click', function() {
            showEducationModal();
        });
    }
    
    // Add Experience Button
    const addExperienceBtn = document.getElementById('add-experience-btn');
    const firstExperienceBtn = document.getElementById('first-experience-btn');
    
    if (addExperienceBtn) {
        addExperienceBtn.addEventListener('click', function() {
            showExperienceModal();
        });
    }
    
    if (firstExperienceBtn) {
        firstExperienceBtn.addEventListener('click', function() {
            showExperienceModal();
        });
    }
    
    // Add Certification Button
    const addCertificationBtn = document.getElementById('add-certification-btn');
    const firstCertificationBtn = document.getElementById('first-certification-btn');
    
    if (addCertificationBtn) {
        addCertificationBtn.addEventListener('click', function() {
            showCertificationModal();
        });
    }
    
    if (firstCertificationBtn) {
        firstCertificationBtn.addEventListener('click', function() {
            showCertificationModal();
        });
    }
    
    // Profile Image Upload
    const profileUpload = document.getElementById('profile-upload');
    if (profileUpload) {
        profileUpload.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                const formData = new FormData();
                formData.append('profile_image', this.files[0]);
                
                fetch('/upload_profile_image', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Refresh the profile image
                        const profileAvatar = document.querySelector('.profile-avatar');
                        profileAvatar.innerHTML = `<img src="${data.image_url}" alt="Profile Image" class="img-fluid rounded-circle">`;
                        
                        // Show success message
                        showNotification('Profile image updated successfully', 'success');
                    } else {
                        showNotification('Failed to update profile image', 'error');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showNotification('An error occurred while updating profile image', 'error');
                });
            }
        });
    }
    
    // Helper Functions
    function toggleFormEditing(form, editable) {
        const inputs = form.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            input.disabled = !editable;
        });
    }
    
    function addTag(input, container, className) {
        const value = input.value.trim();
        if (value) {
            // Check if tag already exists
            const existingTags = container.querySelectorAll('.badge');
            let tagExists = false;
            
            existingTags.forEach(tag => {
                if (tag.textContent.trim().toLowerCase() === value.toLowerCase()) {
                    tagExists = true;
                    tag.classList.add('badge-highlight');
                    setTimeout(() => {
                        tag.classList.remove('badge-highlight');
                    }, 2000);
                }
            });
            
            if (!tagExists) {
                const tag = document.createElement('span');
                tag.classList.add('badge', className, 'me-2', 'mb-2');
                tag.textContent = value;
                
                // Add remove button
                const removeBtn = document.createElement('i');
                removeBtn.classList.add('fas', 'fa-times', 'ms-1');
                removeBtn.style.cursor = 'pointer';
                removeBtn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    tag.remove();
                });
                
                tag.appendChild(removeBtn);
                container.appendChild(tag);
                
                // Clear input
                input.value = '';
                input.focus();
                
                // Remove "No tags" message if it exists
                const noTagsMsg = container.querySelector('.text-muted');
                if (noTagsMsg) {
                    noTagsMsg.remove();
                }
            }
        }
    }
    
    function showPublicationModal() {
        // Implementation would depend on your modal structure
        console.log('Show publication modal');
        // You would typically show a Bootstrap modal here
    }
    
    function showEducationModal() {
        // Implementation would depend on your modal structure
        console.log('Show education modal');
    }
    
    function showExperienceModal() {
        // Implementation would depend on your modal structure
        console.log('Show experience modal');
    }
    
    function showCertificationModal() {
        // Implementation would depend on your modal structure
        console.log('Show certification modal');
    }
    
    function showNotification(message, type) {
        // Implementation would depend on your notification system
        console.log(`${type}: ${message}`);
        // You could use a toast notification or alert system here
    }
});