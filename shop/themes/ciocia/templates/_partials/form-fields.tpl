{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
{* Only the password field changes; every other field comes from Classic's template. *}
{extends file='parent:_partials/form-fields.tpl'}

{*
 * As on the source: an eye icon button instead of the "Pokaż" text. Classic's script replaces the
 * button's text, which would remove the icon, so the button has its own data-action, handled in
 * assets/js/custom.js. The accessible name says what a click will do and changes with the state.
 * No aria-controls: checkout has two fields with the id "field-password", so it would point to the wrong one.
 *}
{block name='form_field_item_password'}
  <div class="input-group js-parent-focus">
    <input
      id="field-{$field.name}"
      class="form-control js-child-focus js-visible-password"
      name="{$field.name}"
      type="password"
      {if isset($configuration.password_policy.minimum_length)}data-minlength="{$configuration.password_policy.minimum_length}"{/if}
      {if isset($configuration.password_policy.maximum_length)}data-maxlength="{$configuration.password_policy.maximum_length}"{/if}
      {if isset($configuration.password_policy.minimum_score)}data-minscore="{$configuration.password_policy.minimum_score}"{/if}
      {if $field.autocomplete}autocomplete="{$field.autocomplete}"{/if}
      value=""
      pattern=".{literal}{{/literal}5,{literal}}{/literal}"
      {if $field.required}required{/if}
    >
    <span class="input-group-btn">
      <button
        class="btn btn-primary ciocia-password-toggle"
        type="button"
        data-action="ciocia-show-password"
        aria-label="Pokaż hasło"
        data-label-show="Pokaż hasło"
        data-label-hide="Ukryj hasło"
      >
        <i class="material-icons" aria-hidden="true">visibility</i>
      </button>
    </span>
  </div>
{/block}
