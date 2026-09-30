/* =========================================================
   DOM REFERENCES AND CONFIGURATION
   ========================================================= */

const employeeDashboardDocument = document;
const employeeDashboardBody = employeeDashboardDocument.body;
const employeeDashboardConfig = {
    employeeQuoteFormUrl: employeeDashboardBody.dataset.employeeQuoteFormUrl,
    customerSignupUrl: employeeDashboardBody.dataset.customerSignupUrl,
    employeeCustomerDashboardUrl: employeeDashboardBody.dataset.employeeCustomerDashboardUrl,
};

const getEmployeeDashboardElement = (id) => employeeDashboardDocument.getElementById(id);

/* =========================================================
   DASHBOARD SEARCH
   ========================================================= */

function initializeDashboardSearch() {
    const dashboardSearchInput = getEmployeeDashboardElement("globalSearch");
    const clearDashboardSearchButton = getEmployeeDashboardElement("clearDashboardSearchButton");
    const dashboardSearchSuggestions = getEmployeeDashboardElement("searchSuggestions");

    if (!dashboardSearchInput || !clearDashboardSearchButton) {
        return;
    }

    clearDashboardSearchButton.addEventListener("click", () => {
        dashboardSearchInput.value = "";
        if (dashboardSearchSuggestions) {
            dashboardSearchSuggestions.hidden = true;
        }
        dashboardSearchInput.focus();
    });
}

/* =========================================================
   PENDING USER DETAILS
   ========================================================= */

function initializePendingUserDetails() {
    const pendingUserDetailsDialog = getEmployeeDashboardElement("pendingUserDetailsDialog");
    const pendingUserDetailButtons = employeeDashboardDocument.querySelectorAll(
        ".details-pending-user-button",
    );

    pendingUserDetailButtons.forEach((pendingUserDetailButton) => {
        pendingUserDetailButton.addEventListener("click", () => {
            const normalizePendingUserValue = (value) => (
                value && value.trim() ? value.trim() : "—"
            );
            const formatPendingUserRole = (value) => {
                const roleText = normalizePendingUserValue(value);
                return roleText === "—"
                    ? roleText
                    : roleText.charAt(0).toUpperCase() + roleText.slice(1);
            };

            const setPendingUserDetail = (id, value) => {
                const detailElement = getEmployeeDashboardElement(id);
                if (detailElement) {
                    detailElement.textContent = normalizePendingUserValue(value);
                }
            };

            setPendingUserDetail("pendingUserRole", formatPendingUserRole(pendingUserDetailButton.dataset.userRole));
            setPendingUserDetail("pendingUserName", pendingUserDetailButton.dataset.userName);
            setPendingUserDetail("pendingUserCompany", pendingUserDetailButton.dataset.userCompany);
            setPendingUserDetail("pendingUserEmail", pendingUserDetailButton.dataset.userEmail);
            setPendingUserDetail("pendingUserUsername", pendingUserDetailButton.dataset.userUsername);
            setPendingUserDetail("pendingUserPhone", pendingUserDetailButton.dataset.userPhone);
            setPendingUserDetail("pendingUserPhoneExtension", pendingUserDetailButton.dataset.userPhoneExtension);
            setPendingUserDetail("pendingUserCreatedAt", pendingUserDetailButton.dataset.userCreatedAt);
            setPendingUserDetail("pendingUserShippingAddress", pendingUserDetailButton.dataset.userShippingAddress);
            setPendingUserDetail("pendingUserBillingAddress", pendingUserDetailButton.dataset.userBillingAddress);

            if (pendingUserDetailsDialog && pendingUserDetailsDialog.showModal) {
                pendingUserDetailsDialog.showModal();
            }
        });
    });
}

/* =========================================================
   CUSTOMER LOOKUP AND EDITING
   ========================================================= */

function initializeCustomerLookup() {
    const customerLookupDialog = getEmployeeDashboardElement("customerLookupDialog");
    const customerLookupInput = getEmployeeDashboardElement("customerLookupInput");
    const customerLookupResultsBody = getEmployeeDashboardElement("customerLookupResults");
    const customerEditDialog = getEmployeeDashboardElement("customerEditDialog");
    const customerEditId = getEmployeeDashboardElement("customerEditId");
    const customerEditCompany = getEmployeeDashboardElement("customerEditCompany");
    const customerEditName = getEmployeeDashboardElement("customerEditName");
    const customerEditAddress = getEmployeeDashboardElement("customerEditAddress");
    const customerEditCityStateZip = getEmployeeDashboardElement("customerEditCityStateZip");
    const customerEditPhone = getEmployeeDashboardElement("customerEditPhone");
    const customerEditEmail = getEmployeeDashboardElement("customerEditEmail");
    const customerEditMessage = getEmployeeDashboardElement("customerEditMessage");
    const customerNotesDialog = getEmployeeDashboardElement("customerNotesDialog");
    const customerNotesText = getEmployeeDashboardElement("customerNotesText");
    const customerNotesMessage = getEmployeeDashboardElement("customerNotesMessage");
    let editingCustomerId = null;
    let notesCustomer = null;
    let customerSearchTimer = null;
    let currentCustomers = [];

    if (!customerLookupDialog || !customerLookupInput || !customerLookupResultsBody) {
        return;
    }

    function renderCustomerResults(customers) {
        currentCustomers = customers;
        customerLookupResultsBody.innerHTML = "";

        if (!customers.length) {
            customerLookupResultsBody.innerHTML = '<tr><td colspan="12">No matches.</td></tr>';
            return;
        }

        customers.forEach((customer) => {
            const customerRow = employeeDashboardDocument.createElement("tr");
            [
                customer.company_name || "—",
                customer.poc || "—",
                customer.address || "—",
                customer.city_state_zip || "—",
                customer.phone || "—",
                customer.email || "—",
                customer.status || "—",
            ].forEach((customerValue) => {
                const customerCell = employeeDashboardDocument.createElement("td");
                customerCell.textContent = customerValue;
                customerRow.appendChild(customerCell);
            });

            const emailCell = employeeDashboardDocument.createElement("td");
            const emailButton = employeeDashboardDocument.createElement(customer.email ? "a" : "button");
            emailButton.className = "employee-dashboard-button secondary employee-dashboard-small-button";
            emailButton.textContent = customer.email ? "Email Customer" : "No Email";
            if (customer.email) {
                emailButton.href = `mailto:${encodeURIComponent(customer.email)}`;
                emailButton.style.textDecoration = "none";
            } else {
                emailButton.type = "button";
                emailButton.disabled = true;
            }
            emailCell.appendChild(emailButton);
            customerRow.appendChild(emailCell);

            ["Attach Quote Form", "Attach Report Images"].forEach((attachmentLabel) => {
                const attachmentCell = employeeDashboardDocument.createElement("td");
                const attachmentButton = employeeDashboardDocument.createElement("button");
                attachmentButton.type = "button";
                attachmentButton.className = "employee-dashboard-button secondary employee-dashboard-small-button";
                attachmentButton.textContent = attachmentLabel;
                attachmentButton.disabled = true;
                attachmentButton.title = "Attachment workflow has not been implemented yet.";
                attachmentCell.appendChild(attachmentButton);
                customerRow.appendChild(attachmentCell);
            });

            const notesCell = employeeDashboardDocument.createElement("td");
            const notesButton = employeeDashboardDocument.createElement("button");
            notesButton.type = "button";
            notesButton.className = "employee-dashboard-button secondary employee-dashboard-small-button";
            notesButton.textContent = "Notes";
            notesButton.addEventListener("click", () => openCustomerNotes(customer));
            notesCell.appendChild(notesButton);
            customerRow.appendChild(notesCell);

            const customerDashboardCell = employeeDashboardDocument.createElement("td");
            const customerDashboardLink = employeeDashboardDocument.createElement("a");
            customerDashboardLink.className = "employee-dashboard-button secondary employee-dashboard-small-button";
            customerDashboardLink.style.textDecoration = "none";
            customerDashboardLink.textContent = "Dashboard";
            customerDashboardLink.href = employeeDashboardConfig.employeeCustomerDashboardUrl.replace(
                "/0",
                `/${encodeURIComponent(customer.id)}`,
            );
            customerDashboardCell.appendChild(customerDashboardLink);
            customerRow.appendChild(customerDashboardCell);

            const editCell = employeeDashboardDocument.createElement("td");
            const editButton = employeeDashboardDocument.createElement("button");
            editButton.type = "button";
            editButton.className = "employee-dashboard-button secondary employee-dashboard-small-button";
            editButton.textContent = "Edit";
            editButton.addEventListener("click", () => openCustomerEdit(customer));
            editCell.appendChild(editButton);
            customerRow.appendChild(editCell);

            const deleteCell = employeeDashboardDocument.createElement("td");
            const deleteButton = employeeDashboardDocument.createElement("button");
            deleteButton.type = "button";
            deleteButton.className = "employee-dashboard-button secondary employee-dashboard-small-button";
            deleteButton.textContent = "Delete";
            deleteButton.addEventListener("click", () => deleteCustomer(customer));
            deleteCell.appendChild(deleteButton);
            customerRow.appendChild(deleteCell);

            const signupCell = employeeDashboardDocument.createElement("td");
            if (customer.status === "Customer") {
                const signupLink = employeeDashboardDocument.createElement("a");
                signupLink.className = "employee-dashboard-button employee-dashboard-small-button";
                signupLink.style.textDecoration = "none";
                signupLink.textContent = "Sign Up";
                const signupUrl = new URL(employeeDashboardConfig.customerSignupUrl, window.location.origin);
                signupUrl.searchParams.set("return_to", window.location.href);
                signupUrl.searchParams.set("name", customer.name || "");
                signupUrl.searchParams.set("address", customer.address || "");
                signupUrl.searchParams.set("phone", customer.phone || "");
                signupUrl.searchParams.set("email", customer.email || "");
                signupLink.href = signupUrl.toString();
                signupCell.appendChild(signupLink);
            }
            customerRow.appendChild(signupCell);
            customerLookupResultsBody.appendChild(customerRow);
        });
    }

    async function deleteCustomer(customer) {
        if (!window.confirm(`Delete ${customer.name}?`)) {
            return;
        }

        try {
            const response = await fetch(`/api/customers/${encodeURIComponent(customer.id)}`, {
                method: "DELETE",
            });
            const responseBody = await response.json().catch(() => ({}));
            if (response.ok && responseBody.ok) {
                currentCustomers = currentCustomers.filter((item) => item.id !== customer.id);
                renderCustomerResults(currentCustomers);
            } else {
                window.alert(responseBody.error || "Delete failed.");
            }
        } catch (error) {
            window.alert("Network error. Please try again.");
        }
    }

    function openCustomerEdit(customer) {
        customerEditMessage.textContent = "";
        editingCustomerId = customer.id;
        customerEditId.value = customer.id;
        customerEditCompany.value = customer.company_name || "";
        customerEditName.value = customer.poc || "";
        customerEditAddress.value = customer.address || "";
        customerEditCityStateZip.value = customer.city_state_zip || "";
        customerEditPhone.value = customer.phone || "";
        customerEditEmail.value = customer.email || "";
        if (customerEditDialog.showModal) {
            customerEditDialog.showModal();
        }
    }

    function openNewCustomer() {
        customerEditMessage.textContent = "";
        editingCustomerId = null;
        customerEditId.value = "";
        customerEditCompany.value = "";
        customerEditName.value = "";
        customerEditAddress.value = "";
        customerEditCityStateZip.value = "";
        customerEditPhone.value = "";
        customerEditEmail.value = "";
        if (customerEditDialog.showModal) {
            customerEditDialog.showModal();
        }
    }

    function openCustomerNotes(customer) {
        notesCustomer = customer;
        customerNotesText.value = customer.notes || "";
        customerNotesMessage.textContent = "";
        if (customerNotesDialog.showModal) {
            customerNotesDialog.showModal();
        }
    }

    async function saveCustomerEdit() {
        const customerId = editingCustomerId;
        const originalCustomer = currentCustomers.find((customer) => String(customer.id) === String(customerId));
        const companyName = customerEditCompany.value.trim() || null;
        const pointOfContact = customerEditName.value.trim() || null;
        const address = customerEditAddress.value.trim() || null;
        const cityStateZip = customerEditCityStateZip.value.trim() || null;
        const phone = customerEditPhone.value.trim() || null;
        const email = customerEditEmail.value.trim() || null;
        const customerPayload = {};

        if (!originalCustomer || originalCustomer.company_name !== companyName) customerPayload.company_name = companyName;
        if (!originalCustomer || (originalCustomer.poc || "") !== pointOfContact) customerPayload.poc = pointOfContact;
        if (!originalCustomer || originalCustomer.address !== address) customerPayload.address = address;
        if (!originalCustomer || originalCustomer.city_state_zip !== cityStateZip) customerPayload.city_state_zip = cityStateZip;
        if (!originalCustomer || originalCustomer.phone !== phone) customerPayload.phone = phone;
        if (!originalCustomer || originalCustomer.email !== email) customerPayload.email = email;

        if (Object.keys(customerPayload).length === 0) {
            customerEditDialog.close();
            return;
        }

        try {
            const response = await fetch(
                customerId ? `/api/customers/${encodeURIComponent(customerId)}` : "/api/customers",
                {
                    method: customerId ? "PATCH" : "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(customerPayload),
                },
            );
            const responseBody = await response.json().catch(() => ({}));
            if (response.ok && responseBody.ok && responseBody.customer) {
                customerEditDialog.close();
                const customerIndex = currentCustomers.findIndex(
                    (customer) => customer.id === responseBody.customer.id,
                );
                if (customerIndex >= 0) {
                    currentCustomers[customerIndex] = responseBody.customer;
                }
                renderCustomerResults(currentCustomers);
            } else {
                customerEditMessage.textContent = responseBody.error || "Update failed.";
            }
        } catch (error) {
            customerEditMessage.textContent = "Network error. Please try again.";
        }
    }

    async function searchCustomers(searchTerm) {
        if (!searchTerm) {
            customerLookupResultsBody.innerHTML = "";
            currentCustomers = [];
            return;
        }

        try {
            const response = await fetch(`/api/customers/search?q=${encodeURIComponent(searchTerm)}`);
            const responseBody = await response.json();
            if (responseBody.ok) {
                renderCustomerResults(responseBody.customers || []);
            }
        } catch (error) {
            // Ignore transient lookup errors and keep the dialog available.
        }
    }

    function clearCustomerSearch() {
        clearTimeout(customerSearchTimer);
        customerLookupInput.value = "";
        customerLookupResultsBody.innerHTML = "";
        currentCustomers = [];
        customerLookupInput.focus();
    }

    async function showAllCustomers() {
        try {
            const response = await fetch("/api/customers/all");
            const responseBody = await response.json();
            if (responseBody.ok) {
                renderCustomerResults(responseBody.customers || []);
            }
        } catch (error) {
            // Ignore transient lookup errors and keep the dialog available.
        }
    }

    getEmployeeDashboardElement("customerLookupButton").addEventListener("click", () => {
        if (customerLookupDialog.showModal) {
            customerLookupDialog.showModal();
        }
        customerLookupInput.focus();
    });
    getEmployeeDashboardElement("addContactButton").addEventListener("click", openNewCustomer);
    getEmployeeDashboardElement("clearCustomerSearchButton").addEventListener("click", clearCustomerSearch);
    getEmployeeDashboardElement("customerLookupClearX").addEventListener("click", clearCustomerSearch);
    getEmployeeDashboardElement("seeAllContactsButton").addEventListener("click", showAllCustomers);
    getEmployeeDashboardElement("customerEditSaveButton").addEventListener("click", saveCustomerEdit);
    getEmployeeDashboardElement("customerEditEmailButton").addEventListener("click", () => {
        const customerEmail = customerEditEmail.value.trim();
        if (!customerEmail) {
            customerEditMessage.textContent = "No customer email is available.";
            return;
        }
        window.location.href = `mailto:${encodeURIComponent(customerEmail)}`;
    });
    getEmployeeDashboardElement("customerNotesSaveButton").addEventListener("click", async () => {
        if (!notesCustomer) {
            return;
        }
        customerNotesMessage.textContent = "";
        try {
            const response = await fetch(`/api/customers/${encodeURIComponent(notesCustomer.id)}`, {
                method: "PATCH",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({notes: customerNotesText.value}),
            });
            const responseBody = await response.json().catch(() => ({}));
            if (response.ok && responseBody.ok && responseBody.customer) {
                const customerIndex = currentCustomers.findIndex(
                    (customer) => customer.id === responseBody.customer.id,
                );
                if (customerIndex >= 0) {
                    currentCustomers[customerIndex] = responseBody.customer;
                }
                notesCustomer = responseBody.customer;
                customerNotesDialog.close();
            } else {
                customerNotesMessage.textContent = responseBody.error || "Notes could not be saved.";
            }
        } catch (error) {
            customerNotesMessage.textContent = "Network error. Please try again.";
        }
    });
    customerLookupInput.addEventListener("input", () => {
        clearTimeout(customerSearchTimer);
        const searchTerm = customerLookupInput.value.trim();
        if (searchTerm.length < 1) {
            customerLookupResultsBody.innerHTML = "";
            currentCustomers = [];
            return;
        }
        customerSearchTimer = setTimeout(() => searchCustomers(searchTerm), 250);
    });
}

/* =========================================================
   BULK CUSTOMER IMPORT
   ========================================================= */

function initializeBulkCustomerImport() {
    const bulkContactsDialog = getEmployeeDashboardElement("addBulkContactsDialog");
    const bulkContactsFileInput = getEmployeeDashboardElement("bulkContactsFileInput");
    const bulkContactsFileName = getEmployeeDashboardElement("bulkContactsFileName");
    const bulkContactsUploadButton = getEmployeeDashboardElement("bulkContactsUploadButton");
    const bulkContactsStatus = getEmployeeDashboardElement("bulkContactsStatus");
    let selectedBulkContactsFile = null;

    getEmployeeDashboardElement("addAccountButton").addEventListener("click", () => {
        window.location.assign(
            `${employeeDashboardConfig.customerSignupUrl}?return_to=${encodeURIComponent(window.location.href)}`,
        );
    });
    getEmployeeDashboardElement("addBulkContactsButton").addEventListener("click", () => {
        if (bulkContactsDialog.showModal) {
            bulkContactsDialog.showModal();
        }
    });
    getEmployeeDashboardElement("bulkImportListButton").addEventListener("click", () => {
        bulkContactsFileInput.click();
    });
    bulkContactsFileInput.addEventListener("change", () => {
        selectedBulkContactsFile = bulkContactsFileInput.files[0] || null;
        bulkContactsFileName.textContent = selectedBulkContactsFile ? selectedBulkContactsFile.name : "";
        bulkContactsUploadButton.style.display = selectedBulkContactsFile ? "inline-block" : "none";
        bulkContactsStatus.textContent = "";
    });
    bulkContactsUploadButton.addEventListener("click", async () => {
        if (!selectedBulkContactsFile) {
            return;
        }
        const bulkContactsFormData = new FormData();
        bulkContactsFormData.append("file", selectedBulkContactsFile);
        bulkContactsStatus.textContent = "Uploading...";
        try {
            const response = await fetch("/api/customers/bulk-import", {
                method: "POST",
                body: bulkContactsFormData,
            });
            const responseBody = await response.json().catch(() => ({}));
            if (response.ok && responseBody.ok) {
                bulkContactsStatus.textContent = `Imported ${responseBody.imported} contacts${
                    responseBody.skipped ? ` (${responseBody.skipped} skipped)` : ""
                }.`;
            } else {
                bulkContactsStatus.textContent = responseBody.error || "Import failed.";
            }
        } catch (error) {
            bulkContactsStatus.textContent = "Network error. Please try again.";
        }
    });
}

/* =========================================================
   NEW QUOTE AND PENDING QUOTE ACTIONS
   ========================================================= */

function initializePendingQuoteActions() {
    employeeDashboardDocument.querySelectorAll(".accept-pending-button").forEach((acceptPendingButton) => {
        acceptPendingButton.addEventListener("click", async () => {
            const pendingQuoteRow = acceptPendingButton.closest("tr");
            const acceptMessage = pendingQuoteRow.querySelector(".accept-message");
            const acceptUrl = acceptPendingButton.getAttribute("data-accept-url");
            const pendingQuoteId = pendingQuoteRow.getAttribute("data-pending-id");

            acceptPendingButton.disabled = true;
            acceptMessage.textContent = "";
            try {
                const response = await fetch(acceptUrl, {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {Accept: "application/json"},
                });
                if (response.status === 200) {
                    window.location.replace(
                        `${employeeDashboardConfig.employeeQuoteFormUrl}?quote_id=${encodeURIComponent(pendingQuoteId)}&accepted=1`,
                    );
                    return;
                }
                if (response.status === 409) {
                    acceptMessage.textContent = "Already claimed by another employee";
                    setTimeout(() => pendingQuoteRow.remove(), 1500);
                    return;
                }
                const responseBody = await response.json().catch(() => ({}));
                acceptMessage.textContent = responseBody.error || "Could not accept quote.";
            } catch (error) {
                acceptMessage.textContent = "Network error. Please try again.";
            } finally {
                acceptPendingButton.disabled = false;
            }
        });
    });
}

function initializePartsCatalogButton() {
    const partsCatalogButton = getEmployeeDashboardElement("partsCatalogButton");

    if (!partsCatalogButton) {
        return;
    }

    partsCatalogButton.addEventListener("click", () => {
        const partsCatalogUrl = partsCatalogButton.getAttribute("href");

        if (partsCatalogUrl) {
            window.location.assign(partsCatalogUrl);
        }
    });
}

/* =========================================================
   PAGE INITIALIZATION
   ========================================================= */

function initializeEmployeeDashboard() {
    initializeDashboardSearch();
    initializePendingUserDetails();
    initializeCustomerLookup();
    initializeBulkCustomerImport();
    initializePendingQuoteActions();
    initializePartsCatalogButton();
}

document.addEventListener("DOMContentLoaded", initializeEmployeeDashboard);
