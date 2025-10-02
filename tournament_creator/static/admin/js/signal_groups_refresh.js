document.addEventListener('DOMContentLoaded', function() {
    console.log('Signal groups refresh script loaded');

    const refreshBtn = document.getElementById('refresh-groups-btn');
    const groupsPicker = document.getElementById('id_recipient_groups_picker');

    console.log('Refresh button found:', !!refreshBtn);
    console.log('Groups picker found:', !!groupsPicker);

    if (refreshBtn && groupsPicker) {
        refreshBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Refresh button clicked');

            // Disable button and show loading state
            refreshBtn.disabled = true;
            refreshBtn.textContent = 'Refreshing...';

            // Make AJAX request to refresh endpoint
            fetch('/api/refresh-signal-groups/', {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin'
            })
            .then(response => {
                console.log('Response status:', response.status);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Response data:', data);

                if (data.success) {
                    // Get currently selected values
                    const selected = Array.from(groupsPicker.selectedOptions).map(opt => opt.value);
                    console.log('Currently selected groups:', selected);

                    // Clear existing options
                    groupsPicker.innerHTML = '';

                    // Add new options from refreshed groups
                    if (data.groups && data.groups.length > 0) {
                        data.groups.forEach(group => {
                            // Use 'id' (with group. prefix) not 'internal_id'
                            const groupId = group.id || group.internal_id || '';
                            const groupName = group.name || group.title || 'Unnamed Group';

                            console.log('Processing group:', groupName, groupId);

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
                        console.log('Added', data.groups.length, 'groups to picker');
                    } else {
                        console.log('No groups returned from API');
                    }

                    alert(`Successfully refreshed! Found ${data.count} group(s).`);
                } else {
                    console.error('Refresh failed:', data.error);
                    alert(`Failed to refresh groups: ${data.error || 'Unknown error'}`);
                }
            })
            .catch(error => {
                console.error('Error refreshing groups:', error);
                alert('Error refreshing groups: ' + error.message);
            })
            .finally(() => {
                // Re-enable button
                refreshBtn.disabled = false;
                refreshBtn.textContent = 'Refresh Groups';
                console.log('Refresh operation completed');
            });
        });
        console.log('Click event listener attached to refresh button');
    } else {
        console.error('Could not initialize refresh button - missing required elements');
    }
});
