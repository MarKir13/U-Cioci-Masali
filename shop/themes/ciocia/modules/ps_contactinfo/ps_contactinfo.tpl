{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
<section class="ciocia-footer-block ciocia-footer-contact" aria-labelledby="ciocia-footer-title-contact">
  <p class="ciocia-footer-title" id="ciocia-footer-title-contact">
    Kontakt
    <button class="ciocia-footer-toggle collapsed" type="button" data-toggle="collapse"
            data-target="#contact-infos" aria-controls="contact-infos"
            aria-expanded="false" aria-labelledby="ciocia-footer-title-contact">
      <i class="material-icons" aria-hidden="true">expand_more</i>
    </button>
  </p>
  <div id="contact-infos" class="ciocia-footer-list collapse">
    {if $contact_infos.company}
      <p class="ciocia-contact-company">{$contact_infos.company}</p>
    {/if}
    {* Built from parts: the formatted address repeats the shop name above and adds the country. *}
    <address>
      {$contact_infos.address.address1}
      {if $contact_infos.address.address2}<br>{$contact_infos.address.address2}{/if}
      <br>{$contact_infos.address.postcode} {$contact_infos.address.city}
    </address>
    {if $contact_infos.phone}
      <p class="ciocia-contact-line">
        <i class="material-icons" aria-hidden="true">phone</i>
        <a href="tel:{$contact_infos.phone|replace:' ':''}">{$contact_infos.phone}</a>
      </p>
    {/if}
    {if $contact_infos.email && $display_email}
      <p class="ciocia-contact-line">
        <i class="material-icons" aria-hidden="true">mail</i>
        <a href="mailto:{$contact_infos.email}">{$contact_infos.email}</a>
      </p>
    {/if}
  </div>
</section>
