import { ALLOWED_TYPES_TEXT, MAX_UPLOAD_MB, PREFIX_RULES } from '@/lib/uploadHelp';

export function UploadHelp() {
  return (
    <section aria-labelledby="upload-help-h" data-testid="upload-help">
      <h3 id="upload-help-h">How to name your files (demo classifier)</h3>
      <p>
        This demo recognises a document by the start of its file name. Name each file with the prefix for its document type,
        for example <code>pan_card.pdf</code>. Matching ignores upper and lower case.
      </p>
      <div className="table-wrap">
        <table className="data">
          <caption>File name prefixes</caption>
          <thead>
            <tr>
              <th scope="col">File name starts with</th>
              <th scope="col">Recognised as</th>
              <th scope="col">Example</th>
            </tr>
          </thead>
          <tbody>
            {PREFIX_RULES.map((r) => (
              <tr key={r.prefix}>
                <th scope="row">
                  <code>{r.prefix}</code>
                </th>
                <td>{r.label}</td>
                <td>
                  <code>{r.example}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul>
        <li>Allowed file types: {ALLOWED_TYPES_TEXT}.</li>
        <li>Maximum size: {MAX_UPLOAD_MB} MB per file.</li>
        <li>Files must be real PDF, JPG or PNG files. A renamed file of another type is rejected.</li>
        <li>Any other file name is flagged and the case goes to manual review.</li>
      </ul>
    </section>
  );
}
