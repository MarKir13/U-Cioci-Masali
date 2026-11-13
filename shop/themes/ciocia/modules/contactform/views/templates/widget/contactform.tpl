{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
{*
 * Contact form as on the source: heading, e-mail and message, labels above the fields.
 * "Temat" shows only when the shop has more than one contact, and "Załącznik" only when file upload
 * is on. shop-content.php leaves one contact and turns upload off, so neither shows by default.
 *}
<section class="contact-form">
  <form action="{$urls.pages.contact}" method="post" {if $contact.allow_file_upload}enctype="multipart/form-data"{/if}>
    {if $notifications}
      <div class="alert {if $notifications.nw_error}alert-danger{else}alert-success{/if}" role="alert">
        <ul class="mb-0">
          {foreach $notifications.messages as $notif}
            <li>{$notif}</li>
          {/foreach}
        </ul>
      </div>
    {/if}

    {if !$notifications || $notifications.nw_error}
      <section class="form-fields">

        <h2 class="ciocia-contact-form-title">Wyślij wiadomość</h2>

        {if $contact.contacts|count > 1}
          <div class="form-group row">
            <label class="col-md-3 form-control-label required" for="id_contact">{l s='Subject' d='Shop.Forms.Labels'}</label>
            <div class="col-md-6">
              <select name="id_contact" id="id_contact" class="form-control form-control-select">
                {foreach from=$contact.contacts item=contact_elt}
                  <option value="{$contact_elt.id_contact}">{$contact_elt.name}</option>
                {/foreach}
              </select>
            </div>
          </div>
        {else}
          {* The module still needs the contact the message goes to. *}
          {foreach from=$contact.contacts item=contact_elt}
            <input type="hidden" name="id_contact" value="{$contact_elt.id_contact}">
          {/foreach}
        {/if}

        <div class="form-group row">
          <label class="col-md-3 form-control-label required" for="email">{l s='Email address' d='Shop.Forms.Labels'}</label>
          <div class="col-md-6">
            <input
              id="email"
              class="form-control"
              name="from"
              type="email"
              autocomplete="email"
              value="{$contact.email}"
              placeholder="{l s='your@email.com' d='Shop.Forms.Help'}"
              required
            >
          </div>
        </div>

        {if $contact.orders}
          <div class="form-group row">
            <label class="col-md-3 form-control-label" for="id-order">{l s='Order reference' d='Shop.Forms.Labels'}</label>
            <div class="col-md-6">
              <select id="id-order" name="id_order" class="form-control form-control-select">
                <option value="">{l s='Select reference' d='Shop.Forms.Help'}</option>
                {foreach from=$contact.orders item=order}
                  <option value="{$order.id_order}">{$order.reference}</option>
                {/foreach}
              </select>
            </div>
            <span class="col-md-3 form-control-comment">
              {l s='optional' d='Shop.Forms.Help'}
            </span>
          </div>
        {/if}

        {if $contact.allow_file_upload}
          <div class="form-group row">
            <label class="col-md-3 form-control-label" for="file-upload">{l s='Attachment' d='Shop.Forms.Labels'}</label>
            <div class="col-md-6">
              <input id="file-upload" type="file" name="fileUpload" class="filestyle" data-buttonText="{l s='Choose file' d='Shop.Theme.Actions'}">
            </div>
            <span class="col-md-3 form-control-comment">
              {l s='optional' d='Shop.Forms.Help'}
            </span>
          </div>
        {/if}

        <div class="form-group row">
          <label class="col-md-3 form-control-label required" for="contactform-message">{l s='Message' d='Shop.Forms.Labels'}</label>
          <div class="col-md-9">
            <textarea
              id="contactform-message"
              class="form-control"
              name="message"
              placeholder="{l s='How can we help?' d='Shop.Forms.Help'}"
              rows="5"
              required
            >{if $contact.message}{$contact.message}{/if}</textarea>
          </div>
        </div>

        {if isset($id_module)}
          <div class="form-group row">
            <div class="col-md-12">
              {hook h='displayGDPRConsent' id_module=$id_module}
            </div>
          </div>
        {/if}

      </section>

      <footer class="form-footer ciocia-contact-actions">
        {* Honeypot from Classic: bots fill it in, people never see it. *}
        <input type="text" name="url" value="" class="ciocia-honeypot" tabindex="-1" autocomplete="off" aria-hidden="true">
        <input type="hidden" name="token" value="{$token}" />
        <input class="btn btn-primary" type="submit" name="submitMessage" value="Wyślij wiadomość">
      </footer>
    {/if}

  </form>
</section>
