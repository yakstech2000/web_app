const countrySelect = document.getElementById("country");
const stateSelect = document.getElementById("state");
const citySelect = document.getElementById("city");

// Load countries
csc.Country.getAllCountries().forEach(country => {
    countrySelect.innerHTML += `
        <option value="${country.isoCode}">
            ${country.name}
        </option>`;
});

// Country changed
countrySelect.addEventListener("change", function () {

    stateSelect.innerHTML =
        '<option value="">Select State</option>';

    citySelect.innerHTML =
        '<option value="">Select City</option>';

    csc.State.getStatesOfCountry(this.value)
        .forEach(state => {

            stateSelect.innerHTML += `
                <option value="${state.isoCode}">
                    ${state.name}
                </option>`;

        });

});

// State changed
stateSelect.addEventListener("change", function () {

    citySelect.innerHTML =
        '<option value="">Select City</option>';

    csc.City.getCitiesOfState(
        countrySelect.value,
        this.value
    ).forEach(city => {

        citySelect.innerHTML += `
            <option value="${city.name}">
                ${city.name}
            </option>`;

    });

});