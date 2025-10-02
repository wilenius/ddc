document.addEventListener('DOMContentLoaded', function() {
    const refreshBtn = document.getElementById('refresh-groups-btn');
    const groupsPicker = document.getElementById('id_recipient_groups_picker');

    if (refreshBtn && groupsPicker) {
        refreshBtn.addEventListener('click', function(e) {
            e.preventDefault();

            // Disable button and show loading state
            refreshBtn.disabled = true;
            refreshBtn.textContent = 'Refreshing...';

            // Make AJAX request to refresh endpoint
            fetch('/admin/refresh-signal-groups/', {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Get currently selected values
                    const selected = Array.from(groupsPicker.selectedOptions).map(opt => opt.value);

                    // Clear existing options
                    groupsPicker.innerHTML = '';

                    // Add new options from refreshed groups
                    if (data.groups && data.groups.length > 0) {
                        data.groups.forEach(group => {
                            // Use 'id' (with group. prefix) not 'internal_id'
                            const groupId = group.id || group.internal_id || '';
                            const groupName = group.name || group.title || 'Unnamed Group';

                            if (groupId) {
                                const option = document.createElement('option');
                                option.value = groupId;
                                option.textContent = `${groupName} (${groupId.substring(0, 30)}...)`;

                                // Re-select if it was previously selected
                                if (selected.includes(groupId)) {
                                    option.selected = true;
                                }

                                groupsPicker.appendChild(option);
                            }
                        });
                    }

                    alert(`Successfully refreshed! Found ${data.count} group(s).`);
                } else {
                    alert(`Failed to refresh groups: ${data.error || 'Unknown error'}`);
                }
            })
            .catch(error => {
                alert('Error refreshing groups: ' + error.message);
            })
            .finally(() => {
                // Re-enable button
                refreshBtn.disabled = false;
                refreshBtn.textContent = 'Refresh Groups';
            });
        });
    }
});
